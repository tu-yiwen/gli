# Ogbn-products
## Data Description


The **ogbn-products** dataset is an undirected and unweighted graph, representing an Amazon product co-purchasing networ. Nodes represent products sold in Amazon, and edges between two products indicate that the products are purchased together. 



Statistics:
1. Nodes: 2,449,029
2. Edges: 61,859,140


#### Citation
- Original Source
```

@Misc{Bhatia16,
          author    = {Bhatia, K. and Dahiya, K. and Jain, H. and Kar, P. and Mittal, A. and Prabhu, Y. and Varma, M.},
          title     = {The extreme classification repository: Multi-label datasets and code},
          url       = {http://manikvarma.org/downloads/XC/XMLRepository.html},
          year      = {2016}
        }
```
- Current Version
```
@inproceedings{
  title={Cluster-GCN: An efficient algorithm for training deep and large graph convolutional networks.},
  author={Wei-Lin Chiang, Xuanqing Liu, Si Si, Yang Li, Samy Bengio, and Cho-Jui Hsieh},
  booktitle=ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  pages={257=266},
  year={2019}
}
```

## Available Tasks
### [OGB](https://ogb.stanford.edu/docs/nodeprop/)
- Task type: `NodeClassification`

#### Citation
```
@inproceedings{
  title={Cluster-GCN: An efficient algorithm for training deep and large graph convolutional networks.},
  author={Wei-Lin Chiang, Xuanqing Liu, Si Si, Yang Li, Samy Bengio, and Cho-Jui Hsieh},
  booktitle=ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  pages={257=266},
  year={2019}
}
```

## Preprocessing
The data files and task config file in GLI format are transformed from the OGB implementation. 

### Requirements
The preprocessing code requires the following package.
```
ogb >= 1.1.1
```