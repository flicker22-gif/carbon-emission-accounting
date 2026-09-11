# 碳排放核算工具

企业级碳排放核算系统：录入各厂区水、电、气、柴油等能源消耗数据，按排放因子自动计算碳排放量，并按 **GHG Protocol 范围一 / 二 / 三** 分类汇总，支持导出排放明细 CSV（报告底稿）。

## 技术栈

- **前端**:Next.js 15 + TypeScript(App Router)
- **后端**:Python 3 + FastAPI + SQLAlchemy
- **数据库**:PostgreSQL（本地开发可切换 SQLite)

## 范围分类（GHG Protocol)

| 范围 | 说明 | 预置能源类型 |
|---|---|---|
| 范围一 | 直接排放（自有/控制源燃烧） | 天然气、柴油、汽油、原煤、液化石油气 |
| 范围二 | 外购能源间接排放 | 外购电力、外购热力/蒸汽 |
| 范围三 | 其他间接排放 | 自来水、航空差旅、废弃物处置 |

排放量计算公式:`排放量(tCO₂e) = 活动数据 × 排放因子(kgCO₂e/单位) ÷ 1000`

## 排放因子库(版本化 + 自动匹配)

因子按 **能源类型 + 地区 + 适用年度** 三维版本化维护,适应官方因子逐年更新:

- 录入能耗时只需选择**能源类型**,不绑定具体因子
- 计算时自动匹配:**厂区所在地区因子优先 → 无则回退「全国」兜底;年度取 ≤ 数据期间的最新版本**
- 因子更新后,历史数据**自动按新因子重算**,无需重录
- 无适用因子的记录标记为「未匹配」,不计入汇总并在仪表盘提醒

> 预置因子中标注"示例值"的地区因子,请在正式使用前通过因子管理页或
> `PUT /api/factors/{id}` 替换为官方最新发布值(生态环境部每年发布全国及省级电力因子)。

> ⚠️ 本次升级为表结构变更(因子表加 region/year、记录表存 energy_type)。
> 已有旧库请删除重建:`rm backend/carbon.db`(SQLite)或 `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`(PG),启动时自动重建并写入种子因子。

## 快速开始

### 方式一:Docker Compose(推荐)

```bash
docker compose up --build
```

- 前端：http://localhost:3000
- 后端 API:http://localhost:8000/docs(Swagger)

### 方式二：本地分别启动

```bash
# 1. PostgreSQL(或 export DATABASE_URL=sqlite:///./carbon.db 用 SQLite)
docker compose up db

# 2. 后端
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000

# 3. 前端
cd frontend
cp .env.example .env.local
npm install
npm run dev                          # http://localhost:3000
```

首次启动时自动建表并写入预置排放因子。

## 功能与页面

| 页面 | 功能 |
|---|---|
| `/` 仪表盘 | 总排放量、范围一/二/三分项、按类别/厂区汇总、导出 CSV |
| `/records` | 能耗数据录入（厂区 + 能源类型 + 月份 + 消耗量）、记录管理 |
| `/facilities` | 厂区新增与列表（含所在地区，用于因子匹配） |
| `/factors` | 排放因子库管理：按能源类型/地区筛选、新增、编辑、删除 |

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/facilities` | 厂区列表 / 新增 |
| GET/POST/PUT/DELETE | `/api/factors` | 因子筛选查询（类型/地区/年度/范围）/ 新增 / 更新 / 删除 |
| GET | `/api/factors/energy-types` | 能源类型下拉选项（去重） |
| GET/POST/DELETE | `/api/records` | 能耗记录查询（支持厂区/期间/范围过滤）/ 新增 / 删除 |
| GET | `/api/reports/summary` | 按范围、类别、厂区的汇总（tCO₂e) |
| GET | `/api/reports/export.csv` | 导出排放明细 CSV |

## 目录结构

```
├── docker-compose.yml
├── backend/
│   └── app/
│       ├── main.py            # FastAPI 入口,启动时建表+种子因子
│       ├── models.py          # Facility / EmissionFactor / EnergyRecord
│       ├── schemas.py         # Pydantic 模型
│       ├── services.py        # 因子自动匹配(地区优先+年度最新+全国兜底)
│       ├── seed_factors.py    # 预置排放因子
│       └── routers/           # facilities / factors / records / reports
└── frontend/
    └── app/                   # 仪表盘、数据录入、厂区、因子页
```

## 后续规划

- 完整的 GHG Protocol 报告导出（组织架构边界、基准年、不确定性说明）
- 范围三 15 个类别完整覆盖与自定义活动类型
- 用户权限与多租户、数据审核流
- 排放趋势图表与同比分析
