# bidirectional-selection-sort-lab

三个选择排序版本，以及一条流行说法的更正。

流传很广的「双向选择排序」文章说：一趟同时找最小值和最大值，可以把**比较次数减少大约一半**。
实测不是。比较次数是 **1.00x，完全没有减少**。真正减半的是内层循环的迭代次数——而在 CPython 里
循环控制本身才是贵的部分，所以这个优化确实有效，只是有效的理由和它说的不一样。

```
                  比较次数      元素读取次数      随机数据提速
baseline            1.00x          1.00x           1.00x
bidirectional       1.00x          1.00x           1.2x
fast（缓存极值）     1.00x          4.00x           1.5x
```

## 一张图说清这个更正

![比较次数几乎不动，读取次数下降](assets/comparisons-vs-reads.png)

上排是相对 baseline 的比较次数。随机数据上这个比值在 1.00–1.03 之间——双向扫描多找一次极值，
成本几乎刚好被抵消。下排是元素读取次数：缓存极值后降了 4 倍，**墙钟时间的收益全部来自这里**。
这张图用的是精确计数，不涉及任何计时。

唯一比较次数真会减半的输入是**严格反序**——这时第二个分支永远不成立。那是特例，不是普遍规律。

## 为什么迭代减半确实有用

![同样的比较次数，一半的迭代](assets/mechanism.png)

两个循环，总比较次数完全相同，迭代次数少一半的那个快 **1.28x**。CPython 里每轮循环的开销
（`FOR_ITER`、`STORE_FAST`、边界处理）比一条 `COMPARE_OP` 贵得多，所以「少一次循环、多一次比较」
是划算的交换。

## 各输入形态下的提速

![各输入形态下的提速](assets/speedup-by-shape.png)

7 轮交错的中位数。注意最后两个面板用的是对数纵轴——那不是小效果。

- **随机 / 近似有序**：`fast` 到 1.4–1.7x。未做缓存的 bidirectional 只有 1.2–1.3x，因为不缓存时它
  每次迭代要读四个元素，迭代减半等于白省。
- **反序**：所有双向版本都是 1.8–2.0x。这是比较次数真减半的形态。
- **已排序 / 全等**：60–900x，全部来自 O(n) 前置检查跳过了 O(n²) 的工作。

## 前置检查：判断失败时是免费的

![前置检查的代价与收益](assets/precheck-cost.png)

左图是它在帮不上忙的输入上的代价。三种无序形态落在 0.81–1.09 之间且没有趋势——在噪声内。
本仓库早期草稿曾声称「反序输入会慢 7–13%」，7 轮交错下这个差异分离不出来，该说法已撤回。

右图是它的收益。收益随 n 增长，因为扫描是 O(n)，而它跳过的工作是 O(n²)。

## 用法

```python
from bidsel import selection_sort_fast

selection_sort_fast([0, 5, 3, 2, 2])   # [0, 2, 2, 3, 5]
```

三个版本，相邻两版之间只差一个想法：

| 函数 | 做什么 | 为什么留着 |
|---|---|---|
| `selection_sort` | 每趟一个极值 | 对照组 |
| `selection_sort_bidirectional` | 每趟最小+最大，不缓存 | 单独隔离「双向」本身 |
| `selection_sort_fast` | 双向 + 缓存极值 + 有序前置检查 | 该用的那个 |

**要求：** Python 3.12+（PEP 695 泛型语法）。无第三方依赖。

**接口契约：** 只要求 `__lt__`。代码里没有 `<=`、`>=`，也没有裸 `>`；`a > b` 靠 Python 的
反射回退也能工作，但依赖它就等于把契约建立在未文档化的行为上。

**不作承诺：** `fast` 不是 upstream `selection_sort` 的 drop-in 替换。含 NaN 时不是，而且所有版本
都不稳定。详见 [`docs/CLAIMS.md`](docs/CLAIMS.md)。

## 用计数代替计时

```python
from bidsel import count_operations, selection_sort, selection_sort_bidirectional

count_operations(selection_sort, [3, 1, 2])
# OpCounts(comparisons=3, subscripts=10, swaps=2)

count_operations(selection_sort_bidirectional, [3, 1, 2])
# OpCounts(comparisons=3, subscripts=10, swaps=2)
```

计数是精确且与机器无关的。当一个论断关于「做了多少工作」时，计数能直接定论；秒表只能说明两者
耗时不同，然后引诱你给出错误的因果解释。

## 本仓库遵守的基准规则

每一条都是先踩错才总结出来的：

1. **同一轮内交错跑各版本，比较逐轮比值。** 先跑完 baseline 再跑优化版，测出 1.45x；交错跑是
   1.22x——光顺序就虚高 18.6%。
2. **复制放在计时之外。** 计时 lambda 里放 `deepcopy`，在被替换的那个包里让 n=100 虚高 21%。
3. **给区间，不给点值。** 原来那个单次运行的脚本，n=100 在三次调用间从 0.93x 跳到 1.45x。
4. **绝不用绝对毫秒算加速比。** 它跨不了进程边界。
5. **每个加速比都要指出是哪两个相邻版本隔离出来的。**

`benchmarks/run_all.py --ci` 跑 3 秒的冒烟档并写 `results-ci.json`，CI 不会覆盖正式的 `results.json`。

## 目录

```
bidsel/core.py            三个版本 + count_operations
tests/                    正确性、计数、契约
benchmarks/run_all.py     计时（交错轮次）
benchmarks/ops.py         精确操作计数
benchmarks/mechanism.py   循环控制开销微基准
assets/make_figures.py    四张图
docs/CLAIMS.md            每一个数字，以及它是怎么来的
```

## 运行

```bash
python -m unittest discover -s tests -t . -v    # BIDSEL_FAST=1 缩短穷举
python benchmarks/ops.py
python benchmarks/mechanism.py
python benchmarks/run_all.py
python assets/make_figures.py                   # 需要 matplotlib
```

## 致谢与许可

对照组沿用 [TheAlgorithms/Python](https://github.com/TheAlgorithms/Python/blob/master/sorts/selection_sort.py)
里 `sorts/selection_sort.py` 的写法（MIT，225k+ stars）。双向版本是教科书算法；本仓库的贡献是
测量、归因，以及两处修复（缓存极值、免冗余交换）。

MIT。见 [LICENSE](LICENSE)。
