"""Utility functions.

Download functions for Google Drive come from
https://github.com/pytorch/vision/blob/main/torchvision/datasets/utils.py.
"""
import contextlib
import itertools
import json
import os
import re
import subprocess
import warnings

from typing import (Iterator, Optional, Tuple)
from urllib.parse import urlparse

import dgl
import numpy as np
import requests
import scipy.sparse as sp
import torch
from torch.utils.model_zoo import tqdm

from gli import ROOT_PATH, WARNING_DENSE_SIZE


def _save_response_content(
    content: Iterator[bytes],
    destination: str,
    length: Optional[int] = None,
    verbose: Optional[bool] = False,
) -> None:
    with open(destination,
              "wb") as fh, tqdm(total=length,
                                disable=not verbose) as pbar:
        for chunk in content:
            # filter out keep-alive new chunks
            if not chunk:
                continue

            fh.write(chunk)
            pbar.update(len(chunk))


def _get_google_drive_file_id(url: str) -> Optional[str]:
    parts = urlparse(url)

    if re.match(r"(drive|docs)[.]google[.]com", parts.netloc) is None:
        return None

    match = re.match(r"/file/d/(?P<id>[^/]*)", parts.path)
    if match is None:
        match = re.match(r"id=(?P<id>[^/]*)&export=download", parts.query)
        if match is None:
            return None
        return match.group("id")

    return match.group("id")


def _extract_gdrive_api_response(
        response,
        chunk_size: int = 32 * 1024) -> Tuple[bytes, Iterator[bytes]]:
    content = response.iter_content(chunk_size)
    first_chunk = None
    # filter out keep-alive new chunks
    while not first_chunk:
        first_chunk = next(content)
    content = itertools.chain([first_chunk], content)

    try:
        match = re.search(
            "<title>Google Drive - (?P<api_response>.+?)</title>",
            first_chunk.decode())  # noqa
        api_response = match["api_response"] if match is not None else None
    except UnicodeDecodeError:
        api_response = None
    return api_response, content


def download_file_from_google_drive(g_url: str,
                                    root: str,
                                    filename: Optional[str] = None,
                                    verbose: Optional[bool] = False):
    """Download a Google Drive file from  and place it in root.

    Args:
        g_url (str): Google Drive url of file to be downloaded
        root (str): Directory to place downloaded file in
        filename (str, optional): Name to save the file under. If None, use the
            id of the file.
    """
    # Based on https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url  # noqa pylint: disable=line-too-long

    file_id = _get_google_drive_file_id(g_url)
    root = os.path.expanduser(root)
    if not filename:
        filename = file_id
    fpath = os.path.join(root, filename)

    os.makedirs(root, exist_ok=True)

    url = "https://drive.google.com/uc"
    params = dict(id=file_id, export="download")
    with requests.Session() as session:
        response = session.get(url, params=params, stream=True)

        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                token = value
                break
        else:
            api_response, content = _extract_gdrive_api_response(response)
            token = "t" if api_response == "Virus scan warning" else None

        if token is not None:
            response = session.get(url,
                                   params=dict(params, confirm=token),
                                   stream=True)
            api_response, content = _extract_gdrive_api_response(response)

        if api_response == "Quota exceeded":
            raise RuntimeError(
                f"The daily quota of the file {filename} is exceeded and it "
                f"can't be downloaded. This is a limitation of Google Drive "
                f"and can only be overcome by trying again later.")

        _save_response_content(content, fpath, verbose=verbose)

    # In case we deal with an unhandled GDrive API response, the file should be smaller than 10kB and contain only text  # noqa pylint: disable=line-too-long
    if os.stat(fpath).st_size < 10 * 1024:
        with contextlib.suppress(UnicodeDecodeError), open(fpath) as fh:  # noqa pylint: disable=unspecified-encoding, line-too-long
            text = fh.read()
            # Regular expression to detect HTML. Copied from https://stackoverflow.com/a/70585604  # noqa pylint: disable=line-too-long
            if re.search(
                    r"</?\s*[a-z-][^>]*\s*>|(&(?:[\w\d]+|#\d+|#x[a-f\d]+);)",
                    text):  # noqa
                warnings.warn(
                    f"We detected some HTML elements in the downloaded file. "
                    f"This most likely means that the download triggered an unhandled API response by GDrive. "  # noqa pylint: disable=line-too-long
                    f"Please report this to torchvision at https://github.com/pytorch/vision/issues including "  # noqa pylint: disable=line-too-long
                    f"the response:\n\n{text}")
    elif verbose:
        print(f"Successfully downloaded {filename} to {root} from {g_url}.")


def load_data(path: os.PathLike):
    """Load data from given path.

    Supported file format:
    1. .npz
    2. .npy
    """
    _, ext = os.path.splitext(path)
    if ext in (".npz", ".npy"):
        data = np.load(path, allow_pickle=True)
    else:
        raise NotImplementedError(f"{ext} file is currently not supported.")
    return data


def unwrap_array(array):
    """Unwrap the array.

    This method is to deal with the situation where array is loaded from
    sparse matrix by np.load(), which will wrap array to be a numpy.ndarray.
    """
    try:
        if isinstance(array, np.ndarray):
            if array.dtype.kind not in set("buifc"):
                return array.all()
    except TypeError:
        return None
    return array


class KeyedFileReader():
    """File reader for npz files."""

    def __init__(self):
        """File reader for npz files."""
        self._data_buffer = {}

    def get(self, path, key=None, device="cpu"):
        """Return a torch array."""
        if path not in self._data_buffer:
            raw = load_data(path)
            self._data_buffer[path] = raw
        else:
            raw = self._data_buffer[path]

        if key:
            array = raw.get(key, None)
        else:
            array = raw

        if array is None:
            return None

        assert isinstance(array, np.ndarray)

        array = unwrap_array(array)

        if array is None:
            file_key_entry = path + ":" + key if key else path
            warnings.warn(
                f"Skip reading {file_key_entry} because it is non-numeric.")
            return None

        if sp.issparse(array):
            # Keep the array format to be scipy rather than pytorch
            # because we may need row indexing later.
            if array.getformat() in ("coo", "csr"):
                return array
            else:
                try:
                    return sp.coo_matrix(array)
                except Exception as e:
                    raise TypeError from e
        else:
            return torch.from_numpy(array).to(device=device)


file_reader = KeyedFileReader()


def sparse_to_torch(sparse_array: sp.spmatrix,
                    convert_to_dense=False,
                    device="cpu"):
    """Transform a sparse scipy array to sparse(coo) torch tensor."""
    if convert_to_dense:
        array = sparse_array.toarray()
        return torch.from_numpy(array).to(device)

    else:
        sparse_type = sparse_array.getformat()
        shape = sparse_array.shape
        if sparse_type == "coo":
            i = torch.LongTensor(
                np.vstack((sparse_array.row, sparse_array.col)))
            v = torch.FloatTensor(sparse_array.data)

            coo_tensor = torch.sparse_coo_tensor(i,
                                                 v,
                                                 torch.Size(shape),
                                                 device=device)
            return coo_tensor
        elif sparse_type == "csr":
            sparse_array: sp.csr_matrix
            crow_indices = sparse_array.indptr
            col_indices = sparse_array.indices
            values = sparse_array.data
            csr_tensor = torch.sparse_csr_tensor(crow_indices,
                                                 col_indices,
                                                 values,
                                                 size=torch.Size(shape),
                                                 device=device)
            return csr_tensor
        else:
            raise TypeError(f"Unsupported sparse type {sparse_type}")


def dgl_to_gli(graph: dgl.DGLGraph,
               name: str,
               pdir: os.PathLike = None,
               **kwargs):
    """Dump a dgl graph into gli format."""
    metadata = {"data": {"Node": {}, "Edge": {}, "Graph": {}}}
    metadata.update(kwargs)
    npz = f"{name}.npz"
    data = {}
    if graph.is_multigraph:
        raise NotImplementedError
    if graph.is_homogeneous:
        for k, v in graph.ndata.items():
            entry = f"node_{k}"
            data[entry] = v.cpu().numpy()
            metadata["data"]["Node"][entry] = {"file": npz, "key": entry}
        for k, v in graph.edata.items():
            entry = f"edge_{k}"
            data[entry] = v.cpu().numpy()
            metadata["data"]["Edge"][entry] = {"file": npz, "key": entry}

        # Reserved Entries
        entry = "_Edge"
        data[entry] = torch.stack(graph.edges()).T.cpu().numpy()
        metadata["data"]["Edge"]["_Edge"] = {"file": npz, "key": entry}

    else:

        for node_type in graph.ntypes:
            # Save node id
            entry = f"node_{node_type}_id"
            metadata["data"]["Node"][node_type] = {
                "_ID": {
                    "file": npz,
                    "key": entry
                }
            }
            data[entry] = graph.nodes(node_type).cpu().numpy()
            # Save node features
            for k, v in graph.ndata.items():
                if node_type in v:
                    entry = f"node_{node_type}_{k}"
                    data[entry] = v.cpu().numpy()
                    metadata["data"]["Node"][node_type][entry] = {
                        "file": npz,
                        "key": entry
                    }

        edge_id = 0
        for edge_type in graph.etypes:
            # Save edge id
            entry = f"edge_{edge_type}_id"
            metadata["data"]["Edge"][edge_type] = {
                "_ID": {
                    "file": npz,
                    "key": entry
                },
            }
            u, v = graph.edges(etype=edge_type)
            data[entry] = graph.edge_ids(u, v, edge_type) + edge_id
            edge_id += len(u)
            # Save edges
            entry = f"edge_{edge_type}"
            metadata["data"]["Edge"][edge_type]["_Edge"] = {
                "file": npz,
                "key": entry
            }
            data[entry] = torch.stack(graph.edges(edge_type)).T.cpu().numpy()
            # Save edge features
            for k, v in graph.edata.items():
                # FIXME - AssertionError: Current HeteroNodeDataView
                # has multiple node types, can not be iterated.
                if edge_type in v:
                    entry = f"edge_{edge_type}_{k}"
                    data[entry] = v.cpu().numpy()
                    metadata["data"]["Edge"][entry] = {
                        "file": npz,
                        "key": entry
                    }

    entry = "_NodeList"
    data[entry] = np.ones((1, graph.num_nodes()))
    metadata["data"]["Graph"]["_NodeList"] = {"file": npz, "key": entry}

    entry = "_EdgeList"
    data[entry] = np.ones((1, graph.num_edges()))
    metadata["data"]["Graph"]["_EdgeList"] = {"file": npz, "key": entry}

    # Save file
    os.makedirs(pdir)
    npz_path = os.path.join(pdir, npz)
    metadata_path = os.path.join(pdir, "metadata.json")

    np.savez_compressed(npz_path, **data)
    with open(metadata_path, "w", encoding="utf-8") as fp:
        json.dump(metadata, fp)

    raise NotImplementedError


def download_data(dataset: str, verbose=False):
    """Download dependent data of a configuration (metadata/task) file.

    Args:
        dataset (str): Name of dataset.
        filename (str): Name of configuration file. e.g., `metadata.json`.
        verbose (bool, optional): Defaults to False.
    """
    data_dir = os.path.join(ROOT_PATH, "datasets/", dataset)
    if os.path.isdir(data_dir):
        url_file = os.path.join(data_dir, "urls.json")
    else:
        raise FileNotFoundError(f"cannot find dataset {dataset}.")
    if os.path.exists(url_file):
        with open(url_file, "r", encoding="utf-8") as fp:
            url_dict = json.load(fp)
    else:
        raise FileNotFoundError(f"cannot find url files of {dataset}.")
    for data_file_name, url in url_dict.items():
        data_file_path = os.path.join(data_dir, data_file_name)
        if os.path.exists(data_file_path):
            if verbose:
                print(f"{data_file_path} already exists. Skip downloading.")
            continue
        else:
            _download(url, data_file_path, verbose=verbose)


def _download(url, out, verbose=False):
    """Download url to out by running a wget subprocess or a gdrive downloader.

    Note - This function may generate a lot of unhelpful message.
    """
    parts = urlparse(url)
    if re.match(r"(drive|docs)[.]google[.]com", parts.netloc) is not None:
        root, filename = os.path.split(out)
        download_file_from_google_drive(url, root, filename, verbose)
        return

    if verbose:
        subprocess.run(["wget", "-O", out, url], check=True)
    else:
        subprocess.run(["wget", "-q", "-O", out, url], check=True)


def _sparse_to_dense_safe(array: torch.Tensor):
    """Convert a sparse tensor to dense.

    Throw user warning if the dense array size is larger than 1 G.

    Args:
        array (torch.Tensor): Input tensor.

    Returns:
        torch.Tensor: Dense tensor.
    """
    if array.is_sparse or array.is_sparse_csr:
        array = array.to_dense()
        array_size = array.element_size() * array.nelement()
        if array_size > WARNING_DENSE_SIZE:
            warnings.warn(
                f"Trying to convert a large sparse tensor to a dense tensor. "
                f"The dense tensor occupies {array_size} bytes.")
    return array


def _to_dense(graph: dgl.DGLGraph, feat=None, group=None, is_node=True):
    graph_data = graph.ndata if is_node else graph.edata

    if graph.is_homogeneous:
        if feat:
            graph_data[feat] = _sparse_to_dense_safe(graph_data[feat])
        else:
            for k in graph_data:
                graph_data[k] = _sparse_to_dense_safe(graph_data[k])
    else:
        if feat:
            assert group is not None
            graph.ndata[feat][group] = _sparse_to_dense_safe(
                graph.ndata[feat][group])
        else:
            raise NotImplementedError(
                "Both feat and group should be provided for"
                " heterograph.")

    return graph


def edge_to_dense(graph: dgl.DGLGraph, feat=None, edge_group=None):
    """Convert edge data to dense.

    If both arguments are not provided, edge_to_dense() will try to convert
    all edge features to dense. (This only works for homograph.)

    Args:
        graph (dgl.DGLGraph): graph whose edges will be converted to dense.
        feat (str, optional): feature name. Defaults to None.
        edge_group (str, optional): edge group for heterograph. Defaults to
            None.

    Raises:
        NotImplementedError: If the graph is heterogeneous, feat and
            edge_group cannot be None.
    """
    return _to_dense(graph, feat, edge_group, is_node=False)


def node_to_dense(graph: dgl.DGLGraph, feat=None, node_group=None):
    """Convert node data to dense.

    If both arguments are not provided, node_to_dense() will try to convert
    all node features to dense. (This only works for homograph.)

    Args:
        graph (dgl.DGLGraph): graph whose nodes will be converted to dense.
        feat (str, optional): feature name. Defaults to None.
        node_group (str, optional): node group for heterograph. Defaults to
            None.

    Raises:
        NotImplementedError: If the graph is heterogeneous, feat and
            node_group cannot be None.
    """
    return _to_dense(graph, feat, node_group, is_node=True)


def to_dense(graph: dgl.DGLGraph):
    """Convert data to dense.

    This function only works for homograph.

    Args:
        graph (dgl.DGLGraph): graph whose data will be converted to dense.

    Raises:
        NotImplementedError: If the graph is heterogeneous.
    """
    if graph.is_homogeneous:
        return node_to_dense(edge_to_dense(graph))
    else:
        raise NotImplementedError("to_dense only works for homograph.")
