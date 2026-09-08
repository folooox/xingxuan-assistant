# 星选助手（本地程序）

Windows / Python Tkinter 桌面程序，包含牛奶团购、团购配送、订单发货、对账分析、商品池和设置。

## 运行

安装 Python 3.13，运行 `python -m pip install -r requirements.txt`，然后 `python main.py`。
打包：`python -m PyInstaller --noconfirm 星选助手.spec`。生成的程序位于 `dist/星选助手.exe`。
个性化业务配置放在程序同级的 `config/` 文件夹；源码运行时位于项目根目录，打包运行时位于 EXE 同级。

## 微盟商品池

打开「商品池分析 → 微盟商品池」，填写微盟后台 Weimob Admin Skills 的 API Key，点击连接并保存。
选择商户及商城 / 门店，分页查询或按名称、编码搜索商品。双击商品，逐店搜索并核对商品 ID，折叠显示门店结果。
读取失败单独显示，可再次点击重试。名称搜索后核对 ID 不等同于完整分配关系接口，门店商品改名可能导致漏匹配。
可查看每条商品的完整原始 JSON。空字段显示「未返回」，不自动补零；商城与门店库存分别显示。

协议依据用户提供的 Weimob Admin Skills 1.0.1：`merchants`、`stores`、`goods`，网关为微盟 `wos-skills.weimob.com`。
仅使用该技能的 API Key，无需开放平台应用或 WOS access_token。
该版本未提供商品成本、SKU 明细和商品编辑接口，这些能力目前未实现。
程序不自动下载或执行官方包的更新脚本。

API Key 保存于本机 `config/weimob_admin.json`，已排除 Git 跟踪。请勿把该文件、业务表格或带密钥的配置上传到 GitHub。
原有「门店导出合并」功能保留，可继续处理门店导出的完整字段。
