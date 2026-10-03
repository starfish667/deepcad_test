## 10.1

写完 m1.sh 发现 30 个只输出了 26 个 `.step` 文件，排查到失败的文件 `00000076.json`，让 ai 分析，ai 认为是 Extrude 的时候部分 `profiles` 项为空导致的

```bash
$ grep -n "\"profiles\": \[\]"  m1_sample/00000076.json
487:   "profiles": [], 
716:   "profiles": [], 
756:   "profiles": [], 
796:   "profiles": [], 
```

核查发现还真是

运行 show.py 出现 segfault，依旧依靠 ai 查 segfault 发现调用了 tkinter 然后摸到了 qt，安装 qt 后正常显示图形

使用 ai 辅助解析 Sketch 如何绘制，让它按照论文格式输出了草图绘制指令，方便对照理解也方便讲解汇报

尝试读懂 json 的详细内容，大概每个文件分三个属性，一个 `entities` 里面有 Sketch 和 Extrude 的绘制命令，`profiles` 疑似依靠 `max_point` 和 `min_point` 框定了模型的范围，`sequence` 则是有顺序的安排 Sketch 和 Extrude 最后组合出完整的模型，显然，`entities` 是关键

`entities` 里应该有两种类型，一种 Sketch 一种 Extrude，Extrude 内容没看懂，只看出来 `profiles` 是说明它根据哪张 Sketch 绘制的，尝试参考官方程序如何解析，找到了 `DeepCAD/cadlib/extrude.py`，找到相关代码

```python
    @staticmethod
    def from_dict(all_stat, extrude_id, sketch_dim=256):
        """construct Extrude from json data

        Args:
            all_stat (dict): all json data
            extrude_id (str): entity ID for this extrude
            sketch_dim (int, optional): sketch normalization size. Defaults to 256.

        Returns:
            list: one or more Extrude instances
        """
        extrude_entity = all_stat["entities"][extrude_id]
        assert extrude_entity["start_extent"]["type"] == "ProfilePlaneStartDefinition"

        all_skets = []
        n = len(extrude_entity["profiles"])
        for i in range(len(extrude_entity["profiles"])):
            sket_id, profile_id = extrude_entity["profiles"][i]["sketch"], extrude_entity["profiles"][i]["profile"]
            sket_entity = all_stat["entities"][sket_id]
            sket_profile = Profile.from_dict(sket_entity["profiles"][profile_id])
            sket_plane = CoordSystem.from_dict(sket_entity["transform"])
            # normalize profile
            point = sket_profile.start_point
            sket_pos = point[0] * sket_plane.x_axis + point[1] * sket_plane.y_axis + sket_plane.origin
            sket_size = sket_profile.bbox_size
            sket_profile.normalize(sketch_dim)
            all_skets.append((sket_profile, sket_plane, sket_pos, sket_size))

        operation = EXTRUDE_OPERATIONS.index(extrude_entity["operation"])
        extent_type = EXTENT_TYPE.index(extrude_entity["extent_type"])
        extent_one = extrude_entity["extent_one"]["distance"]["value"]
        extent_two = 0.0
        if extrude_entity["extent_type"] == "TwoSidesFeatureExtentType":
            extent_two = extrude_entity["extent_two"]["distance"]["value"]

        if operation == EXTRUDE_OPERATIONS.index("NewBodyFeatureOperation"):
            all_operations = [operation] + [EXTRUDE_OPERATIONS.index("JoinFeatureOperation")] * (n - 1)
        else:
            all_operations = [operation] * n

        return [Extrude(all_skets[i][0], all_skets[i][1], all_operations[i], extent_type, extent_one, extent_two,
                        all_skets[i][2], all_skets[i][3]) for i in range(n)]
```
这里面的参数也怪抽象，问 ai 了得到了结果

```json
{
    "type": "ExtrudeFeature",
    "name": "Extrude 1",                                      // ← 显示名，不可靠（可能多语言）
    "profiles": [{"profile": "JGC", "sketch": "FFCC..."}],    // ← 拉哪个剖面（可能有好几个）
    "operation": "NewBodyFeatureOperation",                    // ★ b: 布尔操作
    "extent_type": "OneSideFeatureExtentType",                 // ★ u: 拉伸方式
    "extent_one": {"distance": {"value": 0.0025}},             // ★ e1: 正向距离
    "extent_two": {"distance": {"value": 0.0}},                // ★ e2: 反向距离（只有 TwoSides 用）
    "start_extent": {"type": "ProfilePlaneStartDefinition"}    // ← 固定值，官方直接 assert 掉
}
```
论文里讲 $\alpha,\varphi,\gamma,p_x,p_y,p_z$ 都是 Extrude 命令的参数，但是实际上这个参数放在了 Sketch 的 `transform` 字段里，十分狡猾！

Sketch 里面的参数相对好猜，`profiles` 是重点 `JG` 开头的大概是某种神秘代号，没有实际意义，里面的 `loops` 就是论文里的 loops，里面的指令全部都是按照论文的格式写的，简单易懂，只有一个 `reference_vector` 没看懂是啥，还有 `reference_plane`，ai 告诉我前者是圆心到圆弧起点方向的单位向量，而后者总是空的，不知有什么用，看来不重要，值得注意的是 `loops` 字段内部是无序的，而非论文所言的逆时针，而是靠 `Loop.reorder()` 排序的

理解了重要的字段，命令序列就很显然了

为了完成 M1, 清理掉了 `profiles` 字段为空的错误文件，存放到了 `m1/m1_sample_cleaned`，并使用 `m1/analyze.py` 处理得到 `m1.csv`，论文里的 EOS 不算，因为 `cad_vec` 里面也没算，和官方看齐

统计完发现最高操作数量达到 154！和论文里写的明显不符，查了半天才发现在 `macro.py` 里面有

```python
MAX_N_EXT = 10 # maximum number of extrusion
MAX_N_LOOPS = 6 # maximum number of loops per sketch
MAX_N_CURVES = 15 # maximum number of curves per loop
MAX_TOTAL_LEN = 60 # maximum cad sequence length
```
超过 60 的数据全部被清理掉了！
所以我用ai写了个筛选器，筛掉不符合的

## 10.2
以下内容为 ai 生成：

上一节写“超过 60 的数据全部被清理掉了”，这句话**说错了地方**，重新核实了一遍，写清楚。

`json2vec.py` 里确实有超长就跳过的代码：

```python
    if MAX_TOTAL_LEN < cad_vec.shape[0] or cad_vec is None:
        print("exceed length condition:", data_id, cad_vec.shape[0])
        return
```

但这段代码**一次都没触发过**。三个集合对一下：

| 集合 | 数量 |
| --- | --- |
| `data/cad_json`（原始） | 215,093 |
| `train_val_test_split.json`（官方划分名单） | 178,238 |
| `data/cad_vec`（向量化结果） | 179,133 |

| 检查 | 数量 | 说明 |
| --- | --- | --- |
| `cad_json` 里**不在** split 名单的 | **36,855** | 从未被处理过 |
| split 名单里有、却**没有** `.h5` 的 | **0** | 处理了又被丢的：一个都没有 |
| 在 split 名单里的 json | 178,238 | |
| 其中拿到 `.h5` 的 | 178,238 | 全部成功 |

因为 `process_one` 只对 split 名单里的 id 调用：

```python
Parallel(...)(delayed(process_one)(x) for x in all_data["train"])
```

所以筛选发生在**生成 split 名单**那一步，不是 `json2vec.py`。等 `json2vec.py` 拿到名单时，名单里的人已经全合格了，那段 `return` 自然一次也没走到。

抽样验证（两边各抽 500 个）：

| 检查结果 | split 内 | 非 split |
| --- | --- | --- |
| 四个上限内 | **500（100%）** | 37（7.4%） |
| `ext > 10` | 0 | 163（32.6%） |
| `curves > 15` | 0 | 138（27.6%） |
| `loops > 6` | 0 | 94（18.8%） |
| `len > 60` | 0 | 40（8.0%） |
| 没有拉伸 | 0 | 28（5.6%） |

“不合格”和“不在名单里”高度重合，证明筛选确实存在；但非 split 里还剩 7.4% 查不出违反了哪条，说明生成名单时**还有别的规则没找到**。

自己那 30 个样本的去留，四个条件解释得干干净净：

| 检查结果 | 在 split | 数量 | 文件 |
| --- | --- | --- | --- |
| OK | 是 | 23 | — |
| `ext > 10` | 否 | 1 | `00000062` |
| `len > 60` | 否 | 1 | `00000069` |
| `loops > 6` | 否 | 1 | `00000137` |
| 没有拉伸 | 否 | 4 | `00000076` / `00000175` / `00000176` / `00000177` |

最后 `m1/analyze.py` 输出两份：

| 文件 | 样本数 | 说明 |
| --- | --- | --- |
| `m1_all.csv` | 20 | 不筛上限 |
| `m1_lt60.csv` | 17 | 加上四个上限（等价于模拟论文当初怎么挑数据） |

合计对比：

| | seq_len | line | arc | circle | sol | extrude |
| --- | --- | --- | --- | --- | --- | --- |
| 不筛（20 个） | 536 | 242 | 92 | 39 | 97 | 66 |
| 筛后（17 个） | 186 | 57 | 42 | 19 | 39 | 29 |

`seq_len` 536 → 186，说明不筛的话数字会被超限样本撑得很大，和论文对不上。

到此为止为 ai 生成内容

开始做 M2，发现 `DeepCAD/data/train_val_test_split.json` 其实已经选好了用于训练的样本了，直接抽取一百个作为样本重建就可以了

以下内容为 ai 生成：

今天只做 M2，M3 和 PPT 明天再说，先完成再完美。

方案上纠结过改官方 `test.py` 还是自己写脚本。后来自己翻 DeepCAD 源码翻到了 `dataset/cad_dataset.py`，又摸到 `config/configAE.py` 里的 `--data_root`，发现数据根能整个换掉，那就用最省事的路：自制数据根 + `--data_root`，官方代码一行不改。

官方的 `train_val_test_split.json` 有三个键，我只要 `test`。id 是 `0001/00012459` 这种带目录前缀的，这点问了下 ai 确认。

写 `m2.sh` 的时候 bash 不熟，第一版不对，让 ai 帮我看语法（grep 正则、`if`/`then`、`(( ))` 算术、管道子 shell）。`get_sample.py` 用 `random.Random(114514)` 固定种子抽 100 个，stdout 打 id 让 `m2.sh` 去拷 h5，stdout 接管道也是问的 ai。

跑完 `test.py` 拿到 100 个 h5，`export2step` 之后我第一时间 `wc` 了一下，只有 97 个 STEP，少了 `00231240`、`00770426`、`00823562`。让 ai 复核了下原因：前两个连真值都建不出，只有 `00823562` 是真的模型失败。

最后让 ai 把这几个 md 补上。

M1 的 filter_valid.py 有 172 行，但实测真正起作用的只有「Extrude 的 profiles 不能为空」一条，那段环闭合 / 弧 end_angle 的校验在 30 个样本上一次都没触发。它本来就等价于 grep，于是换成 `grep -L`，删掉 filter_valid.py，清洗也并进 m1.sh。

到此为止为 ai 生成内容

开始做 M3, 让 ai 教我如何读取 h5，发现亏大发了，这个东西直接整理好了所有命令，不需要苦哈哈地去解析 json，M1 做得太笨了

模仿官方 `evaluate_ae_cd.py`，计算 CD 的平均，去掉最大最小 10% 的平均，以及中位数

以下内容为 ai 生成：

M3 的推进：

先把 h5 弄明白了——`(长度, 17)` 的矩阵，17 列 = 命令 + 16 个参数，`gt_vec` 是标准答案、`out_vec` 是模型答卷，序列长度直接数 `gt_vec` 的行数（EOS 已切掉）。

跑全量时 export2step 在 `write_step_file` 崩了：原因是有的文件 `vec2CADsolid` 返回 None，却被官方脚本当 shape 用。让 ai 扫出具体是 `00339538`——它 8 个拉伸单独都能建，是布尔合并那步 `.Shape()` 给了 None。

点云生成完我发现只有 8037 个、不是 8052。查下来是 15 个真值本身建不出（5 个抛异常、10 个是空实体），不是漏跑。顺着又问了“建不出来的肯定不止 15 个吧”，把重建那边也全扫了一遍：重建失败 265 个，和真值缺失取并集 276 个拿不到 CD，能算的是 7776。

m3.py 第一版跑出来 ACC 小了几千倍，肉眼就不对。让 ai 一起排查出四处：累加写成 `=`、参数分母用了全命令 ×16（应是每命令自己的子集 Line 2 / Arc 4 / Circle 3 / Ext 11）、没容差、`np.sort` 没原地改。成功判据也从 `shape is not None` 收紧成“包围盒非空”，不然空实体会被算成功。

CD 打算按官方口径：只对能算的样本统计 mean / 去掉最大最小各 10% / median，失败样本单独报，不塞 0 也不塞大数。

分组阈值 ≤20 / ≤40 / >40 在 100 个样本上 long 只剩 1 个，样本太少没法比，还得再定。

pythonocc 那条 deprecation 警告压不掉，翻了下是它 `@deprecated` 装饰器里 `simplefilter("always")` 又把过滤器清空，普通 filter 无效。

到此为止为 ai 生成内容

## 10.3

发现原来的 `m3.py` 效率太低，决定重构，用 numpy 和 Parallel

重构完成，调试了一下差不多能用，让 ai 验收了一下