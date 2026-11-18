这版补上了「iQue DSi 趣音」启动白屏的修复，包括退出后再次打开时遇到的同类问题。已在配套 Windows 测试环境中连续进出三次，返回菜单后的触摸也正常。

修复放在 NAND 内的趣音程序里：初始化还没完成时，先跳过本次声音更新，等对象准备好再继续。不需要靠整体放慢模拟器来绕过，也没有改拼音界面和原来的输入方式。

**已经用上 v0.1.0 的，可以直接升级，不必从原始 NAND 重做。** 下载新版工具包，关闭模拟器后运行：

```sh
python patch.py check-upgrade "nand-pinyin.bin"
python patch.py upgrade "nand-pinyin.bin" "nand-pinyin-v0.1.1.bin"
python patch.py verify "nand-pinyin-v0.1.1.bin"
```

工具只更新趣音，保留原有昵称、签名和其他数据，生成新的 NAND 与回滚文件，不覆盖旧文件。还没打过补丁的，继续按 README 的 `apply` 步骤操作即可。

如果已经在用此前本地测试的趣音修复版，`verify` 通过就不用再打一次。

本次仍然发布**补丁＋工具**，不附完整 NAND、BIOS 或 APK。PictoChat 返回菜单后的触摸仍需配套模拟器修复；Android 官方版和真机不作为本版的兼容性保证。

下载 `ique-dsi-pinyin-v0.1.1.zip`，使用前看 README。遇到问题请带上系统、模拟器版本和复现步骤，不要上传 NAND 或回滚文件。
