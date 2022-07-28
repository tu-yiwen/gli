"""
Utility functions.

References:
https://github.com/pyg-team/pytorch_geometric/blob/
575611f4f5e2209c7923dba977a1eebc207bd2e2/torch_geometric/
graphgym/cmd_args.py
"""
import argparse
import yaml
import os
import fnmatch
import json
import torch.nn.functional as F
from models.gcn import GCN
from models.gat import GAT
from models.monet import MoNet
from models.graph_sage import GraphSAGE
from models.mlp import MLP


Models_need_to_be_densed = ["GraphSAGE", "GAT"]


def generate_model(args, g, in_feats, n_classes, **model_cfg):
    """Generate required model."""
    # create models
    if args.model == "GCN":
        model = GCN(g,
                    in_feats,
                    model_cfg["num_hidden"],
                    n_classes,
                    model_cfg["num_layers"],
                    F.relu,
                    model_cfg["dropout"])
    elif args.model == "GAT":
        heads = ([model_cfg["num_heads"]] * (model_cfg["num_layers"]-1))\
                + [model_cfg["num_out_heads"]]
        model = GAT(g,
                    model_cfg["num_layers"],
                    in_feats,
                    model_cfg["num_hidden"],
                    n_classes,
                    heads,
                    F.elu,
                    model_cfg["dropout"],
                    model_cfg["dropout"],
                    model_cfg["negative_slope"],
                    model_cfg["residual"])
    elif args.model == "MoNet":
        model = MoNet(g,
                      in_feats,
                      model_cfg["num_hidden"],
                      n_classes,
                      model_cfg["num_layers"],
                      model_cfg["pseudo_dim"],
                      model_cfg["num_kernels"],
                      model_cfg["dropout"])
    elif args.model == "GraphSAGE":
        model = GraphSAGE(g,
                          in_feats,
                          model_cfg["num_hidden"],
                          n_classes,
                          model_cfg["num_layers"],
                          F.relu,
                          model_cfg["dropout"],
                          model_cfg["aggregator_type"])
    elif args.model == "MLP":
        model = MLP(in_feats,
                    model_cfg["num_hidden"],
                    n_classes,
                    model_cfg["num_layers"],
                    F.relu,
                    model_cfg["dropout"])
    return model


def parse_args():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(description="train for node\
                                                  classification")
    parser.add_argument("--model-cfg", type=str,
                        default="configs/model_default.yaml",
                        help="The model configuration file path.")
    parser.add_argument("--train-cfg", type=str,
                        default="configs/train_default.yaml",
                        help="The training configuration file path.")
    parser.add_argument("--model", type=str, default="GCN",
                        help="model to be used. GCN, GAT, MoNet,\
                              GraphSAGE, MLP for now")
    parser.add_argument("--dataset", type=str, default="cora",
                        help="dataset to be trained")
    parser.add_argument("--task", type=str,
                        default="task",
                        help="task name for NodeClassification,")
    parser.add_argument("--gpu", type=int, default=-1,
                        help="which GPU to use. Set -1 to use CPU.")
    return parser.parse_args()


def load_config_file(path):
    """Load yaml files."""
    with open(path, "r", encoding="utf-8") as stream:
        try:
            parsed_yaml = yaml.full_load(stream)
            print(parsed_yaml)
            return parsed_yaml
        except yaml.YAMLError as exc:
            print(exc)


def check_multiple_split(dataset):
    """Check whether the dataset has multiple splits."""
    dataset_directory = os.path.dirname(os.path.dirname(os.getcwd())) \
        + "/datasets/" + dataset
    for file in os.listdir(dataset_directory):
        if fnmatch.fnmatch(file, "task*.json"):
            with open(dataset_directory + "/" + file,  encoding="utf-8") as f:
                task_dict = json.load(f)
                if "num_splits" in task_dict and task_dict["num_splits"] > 1:
                    return 1
                else:
                    return 0