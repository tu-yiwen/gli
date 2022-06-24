# Table of Contents

<!-- MarkdownTOC levels="1,2,3" autolink="true" -->

- [Data Standardization](#data-standardization)
    - [Design Objectives](#design-objectives)
        - [Explicit separation of data storage and task configuration](#explicit-separation-of-data-storage-and-task-configuration)
        - [Objects with attribute scheme](#objects-with-attribute-scheme)
        - [Efficient storage](#efficient-storage)
    - [GLB Data Format](#glb-data-format)
        - [Overview](#overview)
        - [Description](#description)
        - [Example](#example)
    - [GLB Task Format](#glb-task-format)
        - [Overview](#overview-1)
        - [Example](#example-1)
    - [Helper Functions](#helper-functions)
    - [Dataset Class Converter](#dataset-class-converter)
- [Submission and Review System](#submission-and-review-system)
    - [Dataset Submission](#dataset-submission)
        - [Auto Tests](#auto-tests)
    - [Dataset Review](#dataset-review)

<!-- /MarkdownTOC -->

# Data Standardization

The central component of the data standardizing pipeline is a definition of the standard GLB file format. The dataset contributors are supposed to convert the raw data into this standard format and submit their dataset in the GLB format. This platform will provide some helper functions to ease this process. This platform will also provide tools to construct Dataset class in popular graph learning libraries out of the GLB format data files.

![flowchart](/img/flowchart.png)

## Design Objectives

There are two main objectives for the design of the GLB file format. 

1. Allow general data loaders that can be widely applicable to different datasets.
2. Be flexible to accommodate various graph-structured data.
3. Efficient storage and access.

### Explicit separation of data storage and task configuration

To achieve the objective 1, we first make an explicit separation between the data storage and the task configuration. We can define different tasks on the same dataset. We can also perform the same task on different datasets. The separation between data and tasks allows us to implement general data loaders binded to certain types of tasks that can be applied to multiple datasets. 

For example, for the `CoraGraphDataset` in DGL, we will store the graph and the node attributes in the data files, while storing the choice of feature and prediction target, as well as the data split in the task config file.


### Objects with attribute scheme

For objective 2, we would like to accommodate various types of graph-structured data, such as multiple graphs, heterogeneous graphs, dynamic graphs, or even hypergraphs, as well as graphs with node attributes and edge attributes.

For this purpose, we treat nodes, edges, and graphs all as objects with attributes. In particular, edges are objects with a special attribute indicating the two end nodes; graphs are objects with a special attribute indicating the list of nodes it contains. Treating the edges and graphs as objects with special attributes makes it easy to extend to different types of data.

On the other hand, being too flexible about what attributes can be included will make it difficult to implement general data loaders in objective 1. We therefore require all the attributes to follow a set of predefined attribute types, such as `int`, `float`, `SparseTensor`, and `_NodeList`. The `_NodeList` type of attribute is the special attribute that indicates the corresponding object is a graph, and its value is defined as a list of node object ids.

When the existing attribute types are not enough to accommodate a certain type of data, we can further expand the predefined attribute types.


### Efficient storage

We can also create separate supporting data files for efficient storage of certain attributes, e.g., high-dim sparse features. In this case, the main data file will only store the index to access the actual attributes in the supporting file. See the implementation of the `SparseTensor` attribute for an example.

## GLB Data Format

The metadata of the graph dataset should be stored in a file named as `metadata.json`, which refers to various npz files storing the actual data. 

### Overview


We predefine 3 **objects**: *Node*, *Edge*, and *Graph* in our framework. Each object may have multiple **attributes**, e.g., features and prediction targets. Users can define attributes except for three reserved attributes: `_Edge`, `_NodeList`, `_EdgeList`. Each user-defined attribute has multiple required properties: description, type, format, file (may with key in a npz file). Besides, users may define extra properties. For reserved attributes, users only need to provide the data location file (may with key in a npz file).

### Description

#### Objects

- Node
	- No required attribute.
- Edge
	- 1 required attribute _Edge
		- `_Edge` is a `DenseTensor` in shape `(2, n_edges)`
- Graph - A graph dataset may contain multiple disconnected graphs.
	- 1 required attribute `_NodeList`
		- `_NodeList` is a 0/1-valued `SparseTensor` or `DenseTensor` in shape `(n_graph, n_node)`
	- 1 optional attribute `_EdgeList`
		- `_EdgeList` is a 0/1-valued `SparseTensor` or `DenseTensor` in shape `(n_graph, n_edge)`

#### Properties (of an attribute)

- `description`
	- A description of the user-defined attribute
- `type`
	- The data type of the attribute
	- e.g., int, float, text, media, ... (We have not designed the indexing of text or media)
- `format`
	- The saving format of the attribute
	- e.g., SparseTensor, DenseTensor, text file, mp3, ... (We have not designed the saving of text or media)
- `file`
	- The file that contains the attribute
	- e.g. “cora.npz”
- `key`
	- The key that indexes the attribute in certain file format like .npz
	- e.g. “node_feats”

### Example

A complete example of `metadata.json` is given below.

```json
{
    "description": "CORA dataset.",
    "data": {
        "Node": {
            "NodeFeature": {
                "description": "Node features of Cora dataset, 1/0-valued vectors.",
                "type": "int",
                "format": "SparseTensor",
                "file": "cora.npz",
                "key": "node_feats"
            },
            "NodeLabel": {
                "description": "Node labels of Cora dataset, int ranged from 1 to 7.",
                "type": "int",
                "format": "DenseArray",
                "file": "cora.npz",
                "key": "node_class",
            }
        },
        "Edge": {
            "_Edge": {
                "file": "cora.npz",
                "key": "edge"
            }
        },
        "Graph": {
            "_NodeList": {
                "file": "cora.npz",
                "key": "node_list"
            },
            "_EdgeList": {
                "file": "cora.npz",
                "key": "edge_list"
            }
        }
    },
    "citation": "@inproceedings{yang2016revisiting,\ntitle={Revisiting semi-supervised learning with graph embeddings},\nauthor={Yang, Zhilin and Cohen, William and Salakhudinov, Ruslan},\nbooktitle={International conference on machine learning},\npages={40--48},\nyear={2016},\norganization={PMLR}\n}"
}
```

## GLB Task Format

The information about a graph learning task (e.g., the train/test splits or the prediction target) should be stored in a *task configuration file* named as `task_[task_name].json`. There could be multiple different tasks for a single graph dataset, such as node classification and link prediction. Node classification with different data split can also be viewed as different tasks.

### Overview

We predefine multiple task types.

- `NodeClassification`
	- Description: this task requires the model to perform classification on each node.
	- The list of required keys in the task configuration file:
		- `description`: task description.
		- `type`: task type (in this case, `NodeClassification`)
		- `feature`: the node attribute used as node feature in this task
		- `target`: the node attribute used as prediction target in this task
		- `num_classes`: the number of classes
		- `train_set`: the training node IDs
		- `val_set`: the validation node IDs
		- `test_set`: the test node IDs
- `GraphClassification`
	- TBA
- `TimeDependentLinkPrediction`
	- TBA

<!-- #TODO: complete this section. -->

### Example

Here is a complete example of the task configuration file for `NodeClassification` on the CORA dataset.

```json
{
    "description": "Node classification on CORA dataset. Planetoid split.",
    "type": "NodeClassification",
    "feature": [
        "Node/NodeFeature"
    ],
    "target": "Node/NodeLabel",
    "num_classes": 7,
    "train_set": {
        "file": "cora_task.npz",
        "key": "train"
    },
    "val_set": {
        "file": "cora_task.npz",
        "key": "val"
    },
    "test_set": {
        "file": "cora_task.npz",
        "key": "test"
    }
}

```

## Helper Functions

Helper functions that convert commonly seen raw data formats into the GLB format. For example, converting a scipy sparse matrix to an edge index.

## Dataset Class Converter

Constructing DGL or PyG dataset classes from standard GLB file.


# Submission and Review System

## Dataset Submission

### Auto Tests

A series of tests will be automatically applied to newly submitted datasets, in order to reduce the dataset review workload.

#### Data loading tests
graph_loading_test: test if glb.graph.read_glb_graph can be applied successfully to load the graph data
task_loading_test: test if glb.graph.read_glb_task can be applied successfully to load the task
combine_graph_task_test: test if glb.dataloading.combine_graph_and_task can be applied successfully to the loaded graph data and task

#### JSON format tests
- Tests on metadata.json:
	- attribute_name_test: test that only reserved attributes start with "_"
	- reserved_attributes_test: test if required reserved attributes are given (we may also require contributers to include description of dataset)
basic_structure_test: test if the json file follows the same structure as we design.
	- unique_test: check the (file, key) pair is unique.

- Tests on task configuration files:
	- feature_format_test: test the feature keys are in the format of "Node/NodeFeature"
	- Write templates for all existings tests. Check if the new task.json follows the same structure as we design. (task.json has basically fixed structure so this check should be easy.)
	- Check the data split is mutually exclusive.
	- Check if the task is supported.
	- unique_test: check the (file, key) pair is unique.


#### Data integrity tests
- unique_id_test: Test if the Node, Edge, and Graph IDs are unique.
- npy_format_test: Test if the data file can be opened as npz or npy file.


#### Task specific tests
(Write one test per task type to ensure the task.json file follows the predefined task format)

- `NodeClassification`
	- Check num_classes exists.
	- Check target exists in metadata.
- `GraphClassification`
	- Check num_classes exists.
	- Check target exists in metadata.
- `TimeDependentLinkPrediction`
	- Check time exists.
	- Check time windows are mutually exclusive.

## Dataset Review