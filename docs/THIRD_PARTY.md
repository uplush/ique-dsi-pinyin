# 第三方说明

## Rime 简体拼音

来源：https://github.com/rime/rime-pinyin-simp

词库采用 Apache License 2.0，完整文本见 `licenses/Apache-2.0-rime.txt`。
补丁中的新增字典由该词库筛选、排序和转为二进制索引而来。显示范围取决于目标系统已有字库。
源词库文件 SHA-256：`e341598343a0f0f2035bb1aafc34a7f3bb7887deeecb3f60796262aaa2983e6b`。
原词库的版权及许可声明仍然适用。
原词库文件另注明，其基础数据衍生自 Android Open Source Project 的 PinyinIME：
`http://android.git.kernel.org/?p=platform/packages/inputmethods/PinyinIME.git`。

## melonDS

来源：https://github.com/melonDS-emu/melonDS/tree/1.1

melonDS 原项目采用 GPL-3.0-or-later，许可文本见 `licenses/GPL-3.0-melonDS.txt`。
`emulator/touch-reset.patch` 描述本次触摸复位的源代码修改；
`tools/build_melonds_touch.py` 可从匹配的原版程序重新生成已验证的二进制修改。
这两个文件及对应模拟器补丁遵循 GPL-3.0-or-later。
发布包只附补丁，不附原版或修改后的完整模拟器程序。

## Python 依赖

工具通过 pip 使用 NumPy、cryptography 和 bsdiff4。它们按各自项目的许可证分发，
本包没有捆绑这些库的代码或二进制。

## 系统组件

原厂系统程序、字体、BIOS 和完整 NAND 不随本项目提供。
BSDIFF 文件必须配合匹配的原始组件使用。设备尾部、个人资料、照片和存档均不作为补丁来源。

本仓库未为自行编写的工具和输入法代码另外指定开源许可证；第三方部分继续遵循上述许可证。
