<div align="center">

<img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/pandas-2.0+-150458?style=for-the-badge&logo=pandas&logoColor=white"/>
<img src="https://img.shields.io/badge/Chart.js-4.4-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white"/>
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>

# 🎬 电影数据分析系统

**Movie Data Analysis System**

> 基于 Python + Web GUI 的电影评分数据分析平台  
> 9大功能页面 · 实时图表 · 增删改查 · 一键启动

[快速开始](#-快速开始) · [功能介绍](#-功能介绍) · [项目结构](#-项目结构) · [技术栈](#-技术栈)

</div>

---

## ✨ 项目简介

本项目是一套功能完整的电影评分数据分析 Web GUI 系统。  
运行 `python app.py` 后浏览器自动打开，无需额外安装框架，所有分析结果以精美的深色主题界面呈现。

**数据集概况：**

| 指标 | 数值 |
|------|------|
| 电影数量 | 25 部 |
| 用户数量 | 200 位 |
| 评分记录 | 3,730 条 |
| 全局均分 | 3.49 / 5.0 |
| 电影类型 | 18 种 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pandas、numpy（需安装）
- 浏览器（Chrome / Edge / Firefox）

### 安装依赖

```bash
pip install pandas numpy
```

### 启动系统

```bash
python app.py
```

浏览器将自动打开 `http://127.0.0.1:8765`，即可使用全部功能。

> **外网访问**：配合 [ngrok](https://ngrok.com) 可将系统暴露至公网，无需云服务器。
> ```bash
> ngrok http 8765
> ```

---

## 📊 功能介绍

系统共包含 **9 大功能页面**，通过左侧导航栏一键切换：

### 主要分析功能

| 页面 | 功能描述 |
|------|----------|
| 📊 **数据概览** | 6项指标卡片，评分段分布条形图，数据清洗报告 |
| ⭐ **评分统计** | 均值 / 中位数 / 众数 / 标准差 / 四分位数，柱状图 + 甜甜圈图 |
| 🏆 **热门排行** | Top 15 均分排行（≥5人评分），稳定性标签，水平条形图 |
| 🎭 **类型分析** | 18种类型雷达图，各类型评分量直方图 |
| 👥 **用户分析** | 长尾分布直方图，活跃/核心/超级用户三级分层统计 |
| 📈 **趋势分析** | 年度均分折线图，月度双轴图（均分 + 评分量） |

### 工具功能

| 页面 | 功能描述 |
|------|----------|
| 🔍 **详情查询** | 按电影ID / 用户ID查询，含评分分布、相关推荐、最爱类型 |
| ⚖️ **电影对比** | 最多6部电影多维对比，Chart.js 柱状图，自动标注最佳 |
| 🗃️ **数据管理** | 电影与评分的增删改查，分页筛选，实时写回 CSV |

---

## 🗂 项目结构

```
movie-analysis-system/
│
├── app.py                 # 主程序（Web服务器 + 所有API）
├── movie_analysis.py      # 命令行版本（菜单交互）
│
├── data/
│   ├── movies.csv         # 电影信息（movieId, title, genres）
│   └── ratings.csv        # 评分记录（userId, movieId, rating, timestamp）
│
├── output/                # 图表输出目录（运行后自动生成）
│
└── README.md
```

---

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| **后端语言** | Python 3.10+ |
| **数据处理** | pandas 2.0、numpy |
| **Web 服务** | Python 标准库 `HTTPServer`（无需 Flask） |
| **前端图表** | Chart.js 4.4（CDN 引入） |
| **前端界面** | 原生 HTML + CSS + JavaScript（单页应用 SPA） |
| **数据格式** | CSV 文件持久化存储 |

---

## 📁 数据格式说明

**movies.csv**

```csv
movieId,title,genres
1,玩具总动员,Adventure|Animation|Children
2,勇敢者游戏,Adventure|Children|Fantasy
```

**ratings.csv**

```csv
userId,movieId,rating,timestamp
1,1,4.0,964982703
1,3,3.5,964981247
```

> `rating` 范围：0.5 ~ 5.0，步长 0.5  
> `timestamp`：UNIX 时间戳（秒）

---

## 🖥 界面预览

系统采用深色专业主题（`#0D1B2A`），侧边栏导航 + 顶部状态栏，所有图表通过 Chart.js 交互式渲染。

**主要页面截图：**

> 运行系统后访问 `http://127.0.0.1:8765` 即可查看完整界面

---

## 📌 注意事项

- `data/` 目录需包含 `movies.csv` 和 `ratings.csv`，系统启动时自动检测
- CRUD 操作会实时修改 CSV 文件，建议操作前备份原始数据
- 删除电影时会**级联删除**该电影的所有评分记录
- 系统默认监听 `127.0.0.1:8765`，如端口冲突请修改 `app.py` 末尾的 `PORT` 变量

---

## 📄 License

[MIT License](LICENSE) © 2026

---

<div align="center">

**大数据与云计算课程设计 · 2026年5月**

如有问题欢迎提 [Issue](../../issues) 或 [Pull Request](../../pulls)

</div>
