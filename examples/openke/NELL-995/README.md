# NELL-995

## Dataset Description

The NELL-995 dataset contains knowledge base relation triples and textual mentions of Freebase entity pairs. It has a total of 592,213 triplets with 14,951 entities and 1,345 unique relationships.

Statistics:
- Nodes: 75492
- Edges: 154213

#### Citation

```
@article{xiong2017deeppath,
  title={Deeppath: A reinforcement learning method for knowledge graph reasoning},
  author={Xiong, Wenhan and Hoang, Thien and Wang, William Yang},
  journal={arXiv preprint arXiv:1707.06690},
  year={2017}
}
```

## Available Tasks

### Knowledge Graph Completion

+ Task type: `EntityLinkPrediction`
    - Predict the tail (head) entity given a pair of relation and head (tail).
+ Task type: `RelationLinkPrediction`
    - Predict the relation edge given a pair of head and tail entities.

#### Citation

##### Link Prediction Task

```
@article{padia2019knowledge,
    title={Knowledge graph fact prediction via knowledge-enriched tensor factorization},
    author={Padia, Ankur and Kalpakis, Konstantinos and Ferraro, Francis and Finin, Tim},
    journal={Journal of Web Semantics},
    volume={59},
    pages={100497},
    year={2019},
    publisher={Elsevier}
}
```

##### Train, Validation, Test Split

```
@inproceedings{han2018openke,
    title={OpenKE: An Open Toolkit for Knowledge Embedding},
    author={Han, Xu and Cao, Shulin and Lv Xin and Lin, Yankai and Liu, Zhiyuan and Sun, Maosong  and Li, Juanzi},
    booktitle={Proceedings of EMNLP},
    year={2018}
}
```

## Preprocessing

The data files and task config file in GLB format are transformed from the [OpenKE](https://github.com/thunlp/OpenKE) implementation.

### Requirements

The preprocessing code requires the following packages.

```
scipy==1.7.1
```