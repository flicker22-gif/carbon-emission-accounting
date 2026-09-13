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

> ⚠️ 表结构变更说明:
> - 因子表 region/year、记录表存 energy_type 的变更:旧库请删除重建
>   (`rm backend/carbon.db` 或 `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`)。
> - 批次导入功能新增 `import_batches`/`import_rows` 表及 `energy_records.batch_id` 列:
>   新表由 `create_all` 自动建立;旧版开发库启动时会幂等补 `batch_id` 列
>   (仅开发便利,正式环境请走迁移工具)。

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
| `/` 仪表盘 | 总排放量、范围一/二/三分项、按类别/厂区汇总、导出 CSV;待确认批次与未匹配记录提醒 |
| `/batches` 批量导入 | 上传各厂区整份月度能耗表 CSV,逐行校验(行号+字段错误),合法行进入同一待确认批次;复核有效记录/错误行/汇总影响后整批确认锁定,或驳回/退回修订 |
| `/records` | 单条能耗补录(厂区 + 能源类型 + 月份 + 消耗量)、手工记录管理;批次导入记录(🔒)已锁定,不可单条改删 |
| `/facilities` | 厂区新增与列表（含所在地区，用于因子匹配） |
| `/factors` | 排放因子库管理：按能源类型/地区筛选、新增、编辑、删除 |

## 批量导入与复核链路(导入—复核—出数)

各厂区每月上报的是**一整份能耗表**,导入按批次管理,而不是拆成几十条手工录入:

1. **导入**:`POST /api/batches/import` 上传 CSV(模板:`GET /api/batches/template.csv`;
   列:厂区编号、厂区名称、能源类型、期间、消耗量、备注)。逐行校验并返回
   **行号 + 字段错误**;合法行进入**同一个待确认批次**,错误行随批保留但永不导入。
   能源类型支持代码(`electricity`)或中文名(`外购电力`),期间接受 `2026-08`、`2026/8`。
2. **去重**:按解析后的单元格内容归一化计算 SHA256,同一内容在未驳回批次中唯一
   (部分唯一索引兜底并发);重复上传返回 409 且不产生任何记录。驳回/退回后同内容可
   重新上传。同一文件内(厂区+能源类型+期间)重复的行也会被判为错误行。
3. **复核**:批次详情含有效记录(动态匹配地区/年度因子)、错误行、确认后汇总影响;
   **未匹配因子的合法行可追踪,但排放量为空、不计入汇总**。
4. **出数**:`confirm` 后整批写入能耗记录并**锁定**,仪表盘与 CSV **默认只计已确认
   数据**(待确认行只存在于批次表,天然不进任何汇总)。修订已确认批次走 `return`:
   删除锁定记录与批次状态变更在**同一事务**完成,不会出现旧汇总与修订数据同时可见。

状态机:`pending → confirmed`(确认)、`pending → rejected`(驳回)、
`confirmed → rejected`(退回修订);其余转换一律 409。

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/facilities` | 厂区列表 / 新增 |
| GET/POST/PUT/DELETE | `/api/factors` | 因子筛选查询（类型/地区/年度/范围）/ 新增 / 更新 / 删除 |
| GET | `/api/factors/energy-types` | 能源类型下拉选项（去重） |
| GET/POST | `/api/records` | 能耗记录查询（支持厂区/期间/范围过滤）/ 手工新增 |
| PUT/DELETE | `/api/records/{id}` | 修改/删除(仅手工记录;批次锁定记录返回 409) |
| POST | `/api/batches/import` | 上传 CSV,逐行校验后生成待确认批次(重复内容 409) |
| GET | `/api/batches`、`/api/batches/{id}` | 批次列表(可按 status 过滤)/ 详情(行明细+因子匹配) |
| GET | `/api/batches/template.csv` | 导入模板下载 |
| POST | `/api/batches/{id}/confirm` | 确认:合法行整批写入正式表并锁定 |
| POST | `/api/batches/{id}/reject` | 驳回待确认批次(不产生记录) |
| POST | `/api/batches/{id}/return` | 退回已确认批次修订(同事务删除其锁定记录) |
| GET | `/api/reports/summary` | 按范围、类别、厂区的汇总(仅已确认;含待确认批次数) |
| GET | `/api/reports/export.csv` | 导出排放明细 CSV(仅已确认记录) |

后端接口测试:`cd backend && pip install -r requirements-dev.txt && pytest`。

## 目录结构

```
├── docker-compose.yml
├── backend/
│   ├── tests/                 # 接口测试:批次状态机/重复提交/部分错误行/锁定
│   └── app/
│       ├── main.py            # FastAPI 入口,启动时建表+种子因子
│       ├── models.py          # Facility / EmissionFactor / EnergyRecord / ImportBatch / ImportRow
│       ├── schemas.py         # Pydantic 模型
│       ├── services.py        # 因子自动匹配(地区优先+年度最新+全国兜底)
│       ├── import_service.py  # CSV 解析校验、内容去重、批次状态机
│       ├── seed_factors.py    # 预置排放因子
│       └── routers/           # facilities / factors / records / batches / reports
└── frontend/
    └── app/                   # 仪表盘、批量导入、数据录入、厂区、因子页
```

## 后续规划

- 完整的 GHG Protocol 报告导出（组织架构边界、基准年、不确定性说明）
- 范围三 15 个类别完整覆盖与自定义活动类型
- 用户权限与多租户、数据审核流
- 排放趋势图表与同比分析
