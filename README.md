# 军民融合油料数据智能分析系统

基于 Streamlit 的油料收发计量、国标损耗分摊与合规判定系统。

## 功能

- **数据录入**：自动完成 VCF 温度修正 → 标准体积 → 质量换算，按国标损耗率（发油 0.1%、运输 0.21%、收油 0.15%）链式分摊三段损耗，支持管理控制系数从严卡控，自动判定合规 / 超损 / 短量；
- **历史查询**：按日期范围、油品类型、异常状态筛选台账记录；
- **统计分析**：总发油量、总损耗、合规率、分油品统计、月度趋势、异常一览。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 部署到 Streamlit Community Cloud

1. 打开 https://share.streamlit.io ，用 GitHub 账号登录；
2. 点击 Create app，选择本仓库，Main file path 填 `app.py`；
3. 点击 Deploy，等待约 1 分钟获得公网网址。

### 开启访问密码（推荐）

App settings → Secrets 添加：`APP_PASSWORD = "你的密码"`，保存后自动生效。

## 注意

- 仓库内数据均为模拟演示数据；
- Streamlit Cloud 免费版文件存储为临时存储，重启后新录入数据回退到仓库初始数据。