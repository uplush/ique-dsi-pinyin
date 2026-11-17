# 神游 DSi 拼音输入法

我给神游 DSi 的系统键盘加了拼音输入，现在可以直接用中文设置昵称和签名，返回菜单后也能正常显示中文昵称。

这次发布的是补丁和应用工具，不附完整 NAND、BIOS 或个人数据。需要自己准备匹配版本的神游 DSi NAND。

## 能做什么

- 昵称、签名支持单字拼音输入，每页显示 9 个候选字，可以左右翻页。
- 键盘标签调整为「中、A、À、@、表情」。中文页替换原来的日文假名页，其余输入类型保留。
- 中文页去掉了无用的大小写按钮和首个候选字下方的短横线，翻到第一页、最后一页时不会继续越界。
- 修复菜单左上角中文昵称显示成问号的问题。

拼音目前只接在系统设置的昵称和签名里，不是全系统输入法，也没有给 PictoChat 的键盘加入拼音。

## 适用范围

目前验证的是 **神游 DSi 中国区系统组件（1.4.6C）和 Windows 版 melonDS 1.1 x64**。具体是否匹配，以工具的组件校验结果为准，不是看到版本号相同就直接写入。

验证时关闭了 JIT、Fast memory 和 Full BIOS boot。其他模拟器版本、开启这些选项的配置、Android 和真机均未完成验证。

发布包还包括 PictoChat 启动及返回菜单的兼容性修改。其中，**返回后触摸失效的修复在 melonDS 程序里，不在 NAND 里**。要复现目前验证过的完整效果，需要同时应用下面的模拟器补丁。

## 给自己的 NAND 打补丁

在电脑上安装 Python 3.11 或更新版本，下载 [Release](https://github.com/uplush/ique-dsi-pinyin/releases) 中的补丁工具包并解压，在解压目录打开终端：

```sh
python -m pip install -r requirements.txt
python patch.py check "nand.bin"
python patch.py apply "nand.bin" "nand-pinyin.bin"
```

`nand.bin` 换成自己的原始镜像路径。镜像需要带有 melonDS 可识别的 `DSi eMMC CID/CPU` 尾部信息。

工具只接受匹配的原始组件；版本不符、已打过补丁、输出文件已存在时会停止。它不会覆盖输入文件，也不会把我的昵称、签名或其他资料写进你的镜像。

### 每台机器的 NAND 不一样，怎么判断能不能用？

工具不要求整份 NAND 的哈希与我的镜像一致。它读取你的镜像自己的设备信息，解密文件系统，再分别校验主机设置、DSi Menu、PictoChat 和 boot2 ARM9 部分的 SHA-256；目标组件全部匹配后才应用补丁。

写入时仍使用你的镜像自己的加密参数，完成后检查目标组件、其他文件和设备尾部信息。昵称、签名等个人资料不同，不会单独导致版本校验失败。整份镜像的哈希只用于检查原文件未变和匹配本地回滚记录。

目前已测试不同个人资料的镜像副本，还没有用另一台真实神游 DSi 的独立 NAND 做跨设备验证。镜像也需要满足工具支持的文件系统布局和尾部格式。

完成后会得到：

- `nand-pinyin.bin`：新生成的 NAND。
- `nand-pinyin.bin.undo.zip`：这次修改的本地回滚数据，请和原始镜像一起留好，不要上传。

关闭模拟器，在 DSi NAND 设置中选用新文件的工作副本，再重新启动。它是 **NAND 镜像，不是 BIOS，也不是 `firmware.bin`**。不要加载修改前的即时存档来验证。

## melonDS 的触摸修复

这个补丁只匹配指定的 **Windows 版 melonDS 1.1 x64** 可执行文件，工具会校验 SHA-256。原版程序请从 [melonDS 官方发布页](https://github.com/melonDS-emu/melonDS/releases/tag/1.1) 获取。

关闭模拟器，保留原程序目录里的配置文件。在补丁工具目录运行下面的命令，把两个示例路径换成自己的实际路径，新程序仍放在原模拟器目录：

```sh
python patch.py emulator "D:/melonDS/melonDS.exe" "D:/melonDS/melonDS-pinyin.exe"
```

后续启动 `melonDS-pinyin.exe`，配合上面的 NAND 使用。输入、输出也可以填写完整路径；新程序应放在原模拟器目录，便于继续使用原来的 portable 配置。

如果提示程序版本不匹配，就不要套用这个补丁。Android 需要修改对应核心并重新编译 APK，本次发布没有附 Android 安装包。

## 怎么输入

进入「主机设置 → 用户信息 → 昵称／签名」，选择第一个「中」标签，输入拼音，再点候选字。需要英文字母、数字或其他符号时切换对应标签即可。

昵称和签名的长度限制仍沿用系统原来的限制。

## 检查与回滚

```sh
python patch.py verify "nand-pinyin.bin"
python patch.py rollback "nand-pinyin.bin" "nand-pinyin.bin.undo.zip" "nand-restored.bin"
```

回滚会生成新文件，保留打过补丁的副本。只有文件仍与刚打完补丁时完全一致，才会应用这份回滚记录；如果模拟器已经保存了新数据，直接使用自己保留的原始备份。

模拟器程序也用同一条 `rollback` 命令，换成对应的 exe 和 undo 文件即可。回滚程序后，原版缺少触摸复位的行为也会恢复。

## 测试和反馈

昵称、签名的中文输入与保存、菜单中文昵称显示，以及 PictoChat 返回后的触摸和按键，已在配套 Windows 测试环境中确认。

发布工具另做了组件一致性、个人资料保留、错误版本拦截和逐字节回滚检查。工具生成的组件与前面手动验证的版本一致；这不代表所有 NAND、手机或模拟器配置都测过。
具体检查项目见 [验证记录](docs/VERIFICATION.txt)。

遇到问题可以提 Issue，写清系统版本、模拟器版本和复现步骤，附界面截图即可。不要把完整 NAND、BIOS 或回滚文件传到 Issue。

## 文件说明与致谢

- `patches/`：系统组件及模拟器的 BSDIFF 补丁和校验清单。
- `patch.py`、`tools/`：应用、验证、回滚和生成补丁的工具。
- `src/`：本次输入法的核心 C 代码和链接脚本，供查看实现；不是任天堂系统的源码。
- `emulator/`：melonDS 触摸复位的源码修改说明。

拼音数据来自 [Rime 简体拼音](https://github.com/rime/rime-pinyin-simp)，已整理成输入法使用的索引；原项目采用 Apache-2.0，许可证随包附上。模拟器部分基于 [melonDS](https://github.com/melonDS-emu/melonDS)，相关源码修改遵循原项目的 GPL-3.0-or-later。其他说明见 [第三方说明](docs/THIRD_PARTY.md)。
