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

运行 show.py 出现 segfault，依旧依靠 ai 查 segfault 发现调用了 tkinter 然后摸到了 qt，