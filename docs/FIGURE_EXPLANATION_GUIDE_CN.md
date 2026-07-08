# 中文图件解释指南：Lake Varese / Monte Martica post-fire runoff screening

_面向 Feynman Learning Technique 的逐图说明：每张 figure 为什么存在、怎么计算、说明什么问题，以及汇报时应该怎样用简单语言讲清楚。Last updated: 2026-07-08._

---

## 📋 快速定位

这份文档解释当前 repository 中用于汇报和 validation 的主要 figures。核心目标不是“把图背下来”，而是让你能用自己的话讲清楚：**rainfall、DTM、land cover、HSG、burn severity proxy、response units、SCS-CN、WEPPcloud** 之间的因果链条。

| 最重要的事实 | 当前值 | 你应该怎样理解 |
| --- | ---: | --- |
| `Local DEM-derived catchment` | 1,311.76 ha | 当前 selected outlet 控制的 local model domain |
| `Official fire perimeter` | 376.25 ha | 官方火场边界，不等于一个 outlet 的 upstream catchment |
| `Official fire inside current catchment` | 280.14 ha, 74.5% | 当前 outlet 只覆盖官方火场的一部分 drainage area |
| `Conservative dNBR burned proxy` | 23.80 ha, 1.8% of catchment | 当前 local SCS-CN 中真正被加 CN 的主要面积很小 |
| `Fire-perimeter upper bound` | 280.76 ha, 21.4% of catchment | 用 official fire overlap 构造的 sensitivity 上限 |
| `Max local SCS-CN runoff-potential change` | 0.281785 mm, 3,696 m³ | conservative dNBR 下最大 event-scale `burned - baseline` |
| `Upper-bound max runoff-potential change` | 5.505 mm, 72,208 m³ | 如果把更大 footprint 当 burned，结果会放大 |
| `WEPPcloud sediment discharge` | 293.0 → 652.6 tonne/yr, +122.7% | WEPPcloud 最强的 fire signal 是 sediment，不是 runoff validation |
| `Spatial validation decision` | `WARN` | 可作为 screening baseline，但不能做 whole-fire 或 calibrated claims |

```mermaid
flowchart LR
    accTitle: Figure Logic Chain
    accDescr: The diagram shows how the project figures move from spatial context to burn proxy, response units, event runoff, uncertainty, and WEPPcloud benchmark.

    context[📋 Locate study area] --> domain[🔍 Define catchment]
    domain --> burn_proxy[📊 Build dNBR proxy]
    burn_proxy --> response_units[⚙️ Create response units]
    response_units --> scs_cn[🔧 Run SCS-CN events]
    scs_cn --> uncertainty[⚠️ Test uncertainty]
    uncertainty --> benchmark[☁️ Compare WEPPcloud]
    benchmark --> message[✅ Screening conclusion]
```

最简单的 Feynman 版本是：我们先确定“水从哪里流到 selected outlet”，再确定“这片地里哪些地方被 burn proxy 影响”，再把地块切成有不同 land cover / HSG / burn class 的 `response units`，最后对 92 个 `rainfall events` 分别计算 `baseline` 和 `burned scenario` 的 `direct runoff Q`，并用 WEPPcloud 看 process-model 中 sediment / water balance 的方向。

---

## 🎓 共同概念

### 什么叫 `figure` 的计算口径

这里的 figures 分成四类。

| 类别 | 主要路径 | 作用 |
| --- | --- | --- |
| Core slide figures | `../latex/fig*.png`, `../latex/workflow_new.png` | 用于 presentation / manuscript 的主线叙事 |
| Validation maps | `../outputs/maps/*.png` | 用于证明 spatial output 不是只靠 visual inspection，而是有 numeric validation 支撑 |
| Sensitivity/support figures | `../outputs/figures/*.png` | 展示 `burn footprint` 和 `runoff response` uncertainty |
| WEPPcloud reference screenshots | `../outputs/models/weppcloud/input_package/screenshots_for_upload_reference/*.png` | 手动 WEPPcloud upload / comparison 的参考图，不是新模型结果 |

### `dNBR`、`burn severity proxy` 和 `field soil burn severity` 不是同一件事

`NBR` 用 Sentinel-2 的 near-infrared 和 shortwave-infrared band 计算，当前脚本使用 `B08` 和 `B12`。`dNBR = pre-fire NBR - post-fire NBR`。项目把 `dNBR` 分类成 `burn_severity_proxy_uint8.tif`，代码含义是 `0=unburned`、`1=low`、`2=moderate`、`3=high`、`255=NoData`。

Feynman 解释：`dNBR` 像一张“植被变化温度计”。它能告诉我们 Sentinel-2 看见的 vegetation-response change，但它不是现场挖土测出来的 `field soil burn severity`。因此所有图中出现的 `burn severity proxy` 都必须说成 proxy，不要说成 ground truth。

### `response units` 和 `CN adjustment` 怎么进入 SCS-CN

Local model 不对整个 catchment 只算一个 Curve Number。它把 `landcover_class × soil_group/HSG × burn_class` 叠加，得到 `runoff_units.gpkg` 和 `outputs/tables/runoff_units.csv`。当前有 11 个 `response units`，总面积 1,311.76 ha，其中 positive burn classes 的 response units 合计约 23.72 ha。

`baseline_parameter` 是 pre-fire / unburned 的 CN。`burned_parameter` 在 burned units 上增加 CN：`burn_class 1` 加 `+4`，`burn_class 2` 加 `+8`，`burn_class 3` 加 `+12`，`burn_class 0` 不变。当前 conservative dNBR 没有 high severity pixels，所以没有 `CN +12` 的实际 area。

### `SCS-CN` 公式在图里意味着什么

代码的 canonical equation 在 `scripts/pipeline_utils.py` 中：

```text
S = 25400 / CN - 254
Ia = 0.20 * S
Q = (P - Ia)^2 / (P + 0.8 * S), if P > Ia
Q = 0, if P <= Ia
```

其中 `P` 是某个 `rainfall event` 的 precipitation depth，`Q` 是 event-scale `direct runoff` depth。每个 event 都分别跑 `baseline` 和 `burned scenario`，图里的 `Delta Q` 或 `ΔQ` 就是 `burned - baseline`。

> ⚠️ **不要误讲：** 当前 local result 是 screening-level, uncalibrated `runoff-potential change`。它不是 observed discharge，不是 calibrated forecast，也不能直接和 WEPPcloud 的 annual `stream discharge` 当成同一个变量比较。

---

## 📊 逐图数据解码：source fields, units, visual encoding

这一节专门回答“图里的数据到底是什么”。读图时请按四步走：先看 **source data**，再看 **field / unit**，再看 **visual encoding**，最后才看 conclusion。这样可以避免把 context map 误读成 model result，或把 proxy map 误读成 field observation。

### Core figures 的数据细节

| Figure | Source data | Figure data / units | Visual encoding and reading order |
| --- | --- | --- | --- |
| `workflow_new.png` | Pipeline summary from processed outputs and WEPPcloud comparison | Counts / labels: `1,311.76 ha`, `3 definitions`, `6 classes`, `92 events`, `11 units`, `368 scenarios`, `5 sources` | Read left-to-right. Left branch is local `SCS-CN`; right branch is manual `WEPPcloud` benchmark. It is workflow metadata, not a numerical result chart. |
| `fig01a_north_Italy.png` | Natural Earth countries/lakes plus project `STUDY_BOUNDS` | Longitude/latitude in `EPSG:4326`; study box `(8.70, 45.78, 8.92, 45.94)` | Read as location only: Italy → Lombardy → Lake Varese / Varese → study area box. Do not use it for metric measurement. |
| `fig01c_local_domain.png` | `catchment_utm32.gpkg`, official fire perimeter, hydrography, Lake Varese, DEM hillshade | Coordinates in metres, `EPSG:32632`; catchment 1,311.76 ha; official fire 376.25 ha; fire outside current catchment 25.5% | First identify black catchment boundary, then orange/red official fire, then outlet symbols. The hatched / excluded fire part explains why one outlet does not represent the whole fire. |
| `fig02_dem_hydrology_qa.png` | DTM5-derived `dem_utm32.tif`, `flow_accumulation.tif`, `streams_from_dem.gpkg`, official hydrography | DEM elevation in metres; D8 flow accumulation in cells; outlet FA percentile 99.787%; outlet-to-official-hydro distance 79.71 m | Read background terrain first, then DEM streams vs official hydrography, then outlet. The star near high accumulation supports plausibility, not field validation. |
| `fig03_response_units_map.png` | `runoff_units.gpkg` with `baseline_parameter`, `burned_parameter`, `burn_class`, `landcover_class` | `CN adjustment = burned_parameter - baseline_parameter`; dimensionless values 0, +4, +8, +12 | Read colors as parameter change, not burn area by itself. Most catchment is ΔCN 0; colored patches show where burn-related CN adjustment enters SCS-CN. |
| `fig04_response_unit_cn_adjustment.png` | Grouped `runoff_units.gpkg` / `outputs/tables/runoff_units.csv` | Area in ha by `landcover_class × burn_class`; CN change dimensionless | Read bar length as area, bar color / label as CN increase. The largest adjusted units are Forest low severity (~11 ha), Shrub low severity (~8 ha), and Shrub moderate severity (~5 ha). |
| `fig04_event_rainfall_response.png` | `post_fire_rainfall_events.csv` joined to `runoff_delta_by_event.csv` | X = `total_precip_mm`; Y = `delta_runoff_mm`; event IDs are `RAIN_001`–`RAIN_092` | Each point is one rainfall event. The highlighted `RAIN_053` is the largest event: 238.6 mm over 11 days, with max ΔQ 0.281785 mm. |
| `fig05_burn_footprint_area.png` | `burn_severity_ensemble_summary.csv` | `burned_area_ha` by scenario: 23.80, 55.36, 280.76 ha | Read as uncertainty in the input definition: conservative proxy < relaxed threshold < official perimeter upper bound. |
| `fig06_burn_runoff_response.png` | `burn_severity_ensemble_summary.csv` and sensitivity tables | `max_runoff_delta_mm` by scenario: 0.282, 0.690, 5.505 mm | Read as propagated response. It uses the same scenario order as `fig05`, so area uncertainty maps directly into runoff-potential uncertainty. |
| `fig07_event_delta_cdf.png` | `runoff_delta_by_event.csv`, plus ensemble max markers | X = event ΔQ in mm; Y = cumulative fraction of 92 events | Read the blue CDF as “how many observed events are below this ΔQ.” About 79% are below 0.05 mm; vertical lines show max values for alternative footprints. |
| `fig08_sensitivity_hierarchy.png` | `burn_severity_ensemble_summary.csv`, `burn_index_sensitivity_summary.csv`, `rainfall_station_sensitivity.csv`, `scs_initial_abstraction_sensitivity.csv`, `soil_hsg_ensemble_summary.csv` | Each horizontal segment is min–max of max event ΔQ in mm | Read the longest segment as the dominant uncertainty source. `Burned footprint` spans roughly 0.282–5.505 mm, much wider than station, λ, or HSG/CN perturbations. |
| `fig09_weppcloud_sediment.png` | WEPPcloud disturbed / undisturbed outlet summary | Sediment discharge in tonne/yr: 293.0 → 652.6; +122.7% | Read as WEPPcloud-only sediment benchmark. It does not show local SCS-CN runoff and does not validate local ΔQ. |

### Response-unit data behind `fig03` and `fig04`

The response-unit figures are often confusing because they mix maps, land cover, burn class, and Curve Number. The data table below is the simplest way to read them.

| Landcover / burn class | Area shown in figure | Baseline CN | Burned CN / ΔCN |
| --- | ---: | ---: | --- |
| `forest`, `burn_class 1` / Low severity | 10.53 ha | 68 | 72 / `+4` |
| `forest`, `burn_class 2` / Moderate severity | 0.22 ha | 68 | 76 / `+8` |
| `shrub`, `burn_class 1` / Low severity | 7.79 ha | 73 | 77 / `+4` |
| `shrub`, `burn_class 2` / Moderate severity | 4.98 ha | 73 | 81 / `+8` |
| `urban`, `burn_class 1` / Low severity | 0.21 ha | 95 | 98 / `+3` because CN is capped at 98 |
| All `burn_class 0` units | 1,288.04 ha | varies | No burn adjustment |

The important data lesson is that the figure is **area-weighted**. A small high-CN patch does not dominate the catchment if its area is tiny. That is why the final conservative ΔQ remains small even though some burned units receive CN increases.

### Rainfall and event-runoff data behind `fig04_event_rainfall_response` and `fig07`

| Event-data item | Value / field | Meaning in the figure |
| --- | --- | --- |
| Event count | 92 rainfall events | Number of points in `fig04_event_rainfall_response`; number of samples in CDF |
| Event extraction rule | `rain day > 1.0 mm`; one dry day gap | Defines when one event ends and the next begins |
| Rainfall source | Station 907 `Varese v.Appiani` hourly-to-daily sums | Local observed rainfall forcing, not WEPPcloud climate |
| Total event rainfall sum | 2,593.0 mm across 2019–2020 events | Context for local forcing; not an annual WEPPcloud climate value |
| Largest event | `RAIN_053`, 238.6 mm, 11 days | Highlighted point and max ΔQ event |
| Conservative max ΔQ | 0.281785 mm / 3,696 m³ | Largest modelled `burned - baseline` local event difference |
| Median ΔQ | ~0.000888 mm | Explains why CDF rises near zero |
| Events below 0.05 mm | ~79% | Shows most conservative events have very small burn-related ΔQ |

When explaining these figures, avoid saying “runoff increased by 0.282 mm after the fire” without context. The precise statement is: under the current conservative dNBR footprint and SCS-CN assumptions, the **maximum modelled event-scale burned-minus-baseline direct runoff difference** is 0.281785 mm for `RAIN_053`.

### Burn-footprint data behind `fig05`, `fig06`, `fig07`, `fig08`, and burn uncertainty composites

| Scenario | Source type | Burned area | Catchment percent | Max modelled ΔQ |
| --- | --- | ---: | ---: | ---: |
| `conservative_dnbr_proxy` | Sentinel-2 remote-sensing proxy | 23.80 ha | 1.81% | 0.282 mm |
| `relaxed_dnbr_proxy` | Sentinel-2 threshold sensitivity | 55.36 ha | 4.22% | 0.690 mm |
| `official_fire_perimeter_upper_bound` | Regione Lombardia official perimeter upper-bound assumption | 280.76 ha | 21.4% | 5.505 mm |
| `effis_2019_context` | External EFFIS context | 357.20 ha | n/a | n/a |

Only the first three scenarios are used as comparable local model footprint scenarios. `EFFIS` is context because its grid/classes are not equivalent to the Sentinel-2 dNBR product.

### Burn-severity class data behind `outputs/maps/06_burn_severity_proxy_vs_fire_reference.png`

| Raster code | Class name | Area | Percent of valid dNBR pixels | How to read it |
| --- | --- | ---: | ---: | --- |
| `0` | `unburned_or_unchanged` | 385.40 ha | 94.18% | Valid pixel, but no positive burn class |
| `1` | `low_burn_severity_proxy` | 18.60 ha | 4.55% | Positive low dNBR class; CN +4 in local model |
| `2` | `moderate_burn_severity_proxy` | 5.20 ha | 1.27% | Positive moderate dNBR class; CN +8 in local model |
| `3` | `high_burn_severity_proxy` | 0.00 ha | 0.00% | No high severity pixels in conservative proxy |
| `255` | `nodata` | 2,325.84 ha | n/a | Masked / unavailable, not high severity |

This is one of the most important data tables for avoiding misinterpretation. The map may visually show a large grey / blank region, but `255` is NoData; it must not be counted as burned.

### Validation data behind `outputs/maps/08_quantitative_spatial_qa.png`

| Validation check | Status | Data value | Meaning for figure interpretation |
| --- | --- | --- | --- |
| `hydrology_grid_alignment` | PASS | DEM, filled DEM, flow direction, flow accumulation match exactly | D8 hydrology rasters are structurally aligned |
| `burn_raster_domain` | PASS | `uint8`, NoData `255`, classes subset `{0,1,2,3,255}` | Burn raster is structurally valid as categorical raster |
| `fire_inside_current_catchment` | WARN | 74.455% inside current catchment | Current outlet does not cover whole official fire |
| `outlet_flow_accumulation` | PASS | 99.787 percentile | Outlet is plausible on local DEM flow accumulation |
| `soil_resolution` | WARN | HSG-to-DEM pixel-size ratio 12.5 | Soil/HSG is coarse; keep screening language |

The overall validation decision is `WARN`, not `FAIL`. That means the current workflow is usable for selected-outlet screening, but not for whole-fire calibrated claims.

### WEPPcloud data behind `fig09`

| WEPPcloud metric | Undisturbed | Disturbed | Delta | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Watershed area | 1,073.66 ha | 1,073.66 ha | 0 | Both WEPPcloud scenarios use the same watershed |
| Precipitation | 2,872 mm/yr | 2,872 mm/yr | 0 | Same climate forcing in the WEPPcloud comparison |
| Stream discharge | 2,124 mm/yr | 2,125 mm/yr | +1 mm/yr | Annual runoff / stream discharge changes negligibly |
| Hillslope soil loss | 431.3 tonne/yr | 1,157.1 tonne/yr | +168% | Main hillslope erosion signal |
| Sediment discharge | 293.0 tonne/yr | 652.6 tonne/yr | +122.7% | Main figure `fig09` result |
| WEPPcloud burned land use | n/a | 175.7 ha `Low Severity Fire` | n/a | Much larger than local 23.8 ha conservative dNBR proxy |

The data point that matters for the figure is sediment discharge, but the surrounding rows are necessary to explain why this is **sediment benchmark evidence**, not a direct runoff validation. WEPPcloud shows strong sediment response while annual stream discharge is essentially unchanged.

### Supporting screenshots: what data they repeat

The `screenshots_for_upload_reference` images repeat existing local figures inside the WEPPcloud input package. Their data purpose is traceability, not new analysis.

| Screenshot | Repeated data | Why it is included |
| --- | --- | --- |
| `03_final_catchment_fire_hydrography_overlay.png` | Catchment, official fire, outlet, hydrography | Helps manually check WEPPcloud outlet / watershed context |
| `06_burn_severity_proxy_vs_fire_reference.png` | Burn raster classes and official fire perimeter | Helps verify class mapping and NoData before upload |
| `07_runoff_delta_event_main.png` | Response-unit CN adjustment map | Helps explain how local burn proxy affects SCS-CN parameters |
| `rainfall_events_2019.png` | Top rainfall event depths | Documents local observed forcing used in SCS-CN, not WEPPcloud climate |
| `weppcloud_input_package_overview.png` | Package-level metadata | Records zip package, catchment reference, official fire reference, outlet, burn raster, and manual WEPPcloud status |

---

## 📚 Core slide figures

### `latex/workflow_new.png` — Processing workflow

![Processing workflow showing local SCS-CN and WEPPcloud branches](../latex/workflow_new.png)

**图上是什么。** 这张图把项目分成两条 branch：`Path A: Local SCS-CN pipeline` 和 `Path B: External WEPPcloud comparison`。左边从 `DTM5 DEM`、`Fire perimeter / Sentinel-2 L2A`、`DUSAF6`、`SoilGrids`、`ARPA rainfall` 进入 local model；右边从 manual `WEPPcloud setup`、uploaded burn raster and outlet point 进入 WEPPcloud EU，再输出 annual runoff / sediment。

**怎么计算。** 这张 workflow 本身不是数值模型输出，而是对 pipeline 结果的结构化摘要。它把 `catchment and outlet 1,311.76 ha`、`burn scenarios 3 definitions`、`hydrologic land cover 6 classes`、`HSG confirmed`、`rainfall events 92 events`、`response units and CN assignment 11 units`、`SCS-CN event model 368 scenarios`、`sensitivity envelope 5 sources` 放在同一张流程图里。

**为什么存在。** 它替代文字过多的开场页，让 audience 先知道本项目不是只画火场地图，而是一个从 data inputs 到 model outputs 的 reproducible workflow。

**说明的问题。** 它强调 local SCS-CN 和 WEPPcloud 不是同一个模型。Local branch 是 event-based direct runoff screening；WEPPcloud branch 是 manual external process-model benchmark，主要输出 annual water balance 和 sediment。

**Feynman 一句话。** “这张图就是菜谱：左边告诉你 local runoff estimate 怎么从 DEM、land cover、soil、burn proxy 和 rainfall 做出来；右边告诉你 WEPPcloud 怎么作为 benchmark 补充 sediment / water balance 视角。”

**不要这样讲。** 不要说 workflow 证明所有步骤都自动化完成；WEPPcloud 是 manual webpage step。也不要说 WEPPcloud validation 了 local SCS-CN。

### `latex/fig01a_north_Italy.png` — Regional context map

![Regional context map locating Lake Varese and the study area in northern Italy](../latex/fig01a_north_Italy.png)

**图上是什么。** 这是一张 EPSG:4326 的 regional context map，显示 Italy、Lombardy、Lake Varese、Varese 和 study area box。

**怎么计算。** 脚本 `scripts/figures/fig01a_regional_context.py` 下载或读取 Natural Earth countries / lakes 数据，并在 WGS84 经纬度中绘图。`STUDY_BOUNDS = (8.70, 45.78, 8.92, 45.94)` 是用于 regional display 的 study box；Lake Varese 在 Natural Earth 中不一定完整，所以图中还手动近似添加了 Lake Varese ellipse。

**为什么存在。** 先让非本地 audience 知道研究区在 northern Italy / Lombardy / Lake Varese 附近。没有这张图，后面的 UTM 坐标、catchment 和 fire perimeter 对读者来说都没有空间参照。

**说明的问题。** 它说明 study area box 是 location / context，不是 final hydrologic boundary。它也解释为什么后续 browser exchange 或 WEPPcloud visible extent 会用 EPSG:4326。

**Feynman 一句话。** “这张图只是告诉你故事发生在哪里，不告诉你水文学边界在哪里。”

**不要这样讲。** 不要把红色 study area box 当成 catchment，也不要在 EPSG:4326 上计算 area、distance、slope 或 hydrologic routing。

### `latex/fig01c_local_domain.png` — Local analytical domain map

![Local analytical domain map with Lake Varese, candidate subcatchment, fire perimeter, streams, and outlet](../latex/fig01c_local_domain.png)

**图上是什么。** 这张 map 显示 local analytical domain：Lake Varese、official hydrography、DEM-derived streams、`Candidate subcatchment`、`Official fire perimeter`、`Excluded fire (25.5%)`、`Candidate outlet` 和 `Hydro-snapped alternative`。

**怎么计算。** 脚本 `scripts/figures/fig01c_local_domain.py` 读取 `catchment_utm32.gpkg`、`monte_martica_fire_2019_utm32.gpkg`、`streams_lombardia_varese_utm32.gpkg`、`lake_varese_boundary.gpkg`，并以 `dem_utm32.tif` 生成 hillshade 背景。`fire_outside = fire.overlay(catchment, how="difference")` 用来标出 official fire perimeter 中不在当前 catchment 内的部分。

**为什么存在。** 它定义了 current local model domain。最关键的不是“图好看”，而是告诉你：selected outlet 控制的是 1,311.76 ha 的 `Candidate subcatchment`，不是整个 official fire perimeter。

**说明的问题。** Official fire perimeter 有 376.25 ha；其中约 280.14 ha 在当前 catchment 内，约 96.11 ha 在外面。也就是说，one outlet 不能代表 whole official fire interpretation。

**Feynman 一句话。** “这张图告诉我们：一个 outlet 就像一个漏斗口，只能收集流向它的那部分坡面，不会自动收集整个火场。”

**不要这样讲。** 不要说当前 catchment 是最终 field-validated watershed；它仍是 `DEM-derived candidate`，需要 outlet / hydrography review。

### `latex/fig02_dem_hydrology_qa.png` — DEM hydrology validation

![DEM hydrology validation map with hillshade, D8 streams, official hydrography, catchment, and outlet](../latex/fig02_dem_hydrology_qa.png)

**图上是什么。** 这张图叠加 DEM hillshade、terrain color、official hydrography、DEM-derived streams、candidate subcatchment、official fire perimeter 和 candidate outlet。图例中特别标注 outlet 位于 `99.8th FA pct.`，也就是 flow accumulation percentile 很高。

**怎么计算。** `scripts/05_prepare_dem.py` 将 DTM5 DEM 裁剪到 processing AOI，reproject / resample 到 EPSG:32632 的 20 m grid，并用 WhiteboxTools 生成 `filled DEM`、`D8 flow direction`、`flow accumulation` 和 `streams_from_dem.gpkg`。Outlet candidate 在 fire perimeter 附近 2.5 km buffer 内，以高 flow accumulation、低 elevation 的 score 选出。`scripts/figures/fig02_dem_hydrology_qa.py` 再把这些结果画成 validation map。

**为什么存在。** 任何 runoff model 都要先回答“水真的可能流到这个 outlet 吗？”这张图就是 hydrologic plausibility check，不是装饰图。

**说明的问题。** Numeric validation 显示 outlet 到 DEM stream 距离约 0.001 m，到 official hydrography 距离约 79.71 m，flow accumulation percentile 为 99.787%。这支持 outlet hydrologically plausible，但不能替代现场或官方 drainage validation。

**Feynman 一句话。** “这张图是检查漏斗口是不是放在水流会汇集的地方。”

**不要这样讲。** 不要只凭视觉说 overlap 合理；接受依据应来自 `qa/spatial/outlet_plausibility.csv` 和 `qa/spatial/qa_decisions.csv`。

### `latex/fig03_response_units_map.png` — Response units map

![Response units map showing where CN adjustment classes occur](../latex/fig03_response_units_map.png)

**图上是什么。** 图中用颜色显示不同 `CN adjustment` class：`0 (unburned, no adjustment)`、`4 (low severity fire)`、`8 (moderate severity fire)`；`12 (high severity)` 当前没有实际 area。黑色边界是 `Candidate subcatchment`，虚线是 `Official fire perimeter`。

**怎么计算。** `scripts/11_run_simplified_runoff.py` 先生成 `runoff_units.gpkg`：把 DUSAF6-derived `landcover_class`、dominant SoilGrids-derived `HSG`、positive `dNBR burn_class`、DEM slope 和 catchment 叠加。`scripts/figures/fig03_response_units_cn.py` 读取 response units，计算 `burned_parameter - baseline_parameter`，再将 ΔCN 分类为 0、4、8、12。

**为什么存在。** 它把抽象的 CN 参数落到地图上：模型不是“整个 catchment CN 增加一点”，而是只有某些小块 `response units` 发生 CN adjustment。

**说明的问题。** 当前 conservative dNBR 下，被调整的区域集中在火场与 catchment overlap 的一小部分。Positive burn response units 合计约 23.72 ha，远小于 official fire inside catchment 的 280.14 ha。

**Feynman 一句话。** “这张图告诉你模型到底在哪些格子上改变了参数，而不是只告诉你最后数字。”

**不要这样讲。** 不要把所有 official fire polygon 都当作 CN adjusted area；当前 local model 的 adjusted area 来自 positive dNBR classes。

### `latex/fig04_response_unit_cn_adjustment.png` — Burned response units by CN adjustment

![Bar chart of burned response units by CN adjustment](../latex/fig04_response_unit_cn_adjustment.png)

**图上是什么。** 这是 horizontal bar chart，只汇总 burned response units。它显示 Forest / Shrub / Urban 在 `Low severity` 或 `Moderate severity` 下的 area，以及相应 `CN +4`、`CN +8` 或 `CN +3`。

**怎么计算。** `scripts/figures/fig04_response_unit_cn_adjustment.py` 从 `runoff_units.gpkg` 按 `landcover_class` 和 `burn_class` groupby，求每组 `area_m2` 总和，再计算平均 `burned_parameter - baseline_parameter`。当前主要条目是 Forest low severity 约 11 ha、Shrub low severity 约 8 ha、Shrub moderate severity 约 5 ha；Forest moderate 和 Urban low severity 很小。

**为什么存在。** `fig03` 告诉你位置，`fig04_response_unit_cn_adjustment` 告诉你面积和参数变化。两者合起来说明“where”和“how much”。

**说明的问题。** 虽然 official fire perimeter 很大，但真正影响 SCS-CN 参数的 conservative burned units 很少，所以 local runoff delta 小是有原因的。

**Feynman 一句话。** “这张图像账本：每种 burned unit 占多少 ha，CN 被加了多少。”

**不要这样讲。** 不要把这个图解释成 burn severity 的 field survey；它只是 model response units 的 CN adjustment summary。

### `latex/fig04_event_rainfall_response.png` — Rainfall event depth vs modelled runoff response

![Scatter plot of rainfall event depth versus modelled Delta Q](../latex/fig04_event_rainfall_response.png)

**图上是什么。** 横轴是 `Event rainfall depth (mm)`，纵轴是 `Modelled Delta Q (mm)`。每个点代表一个 rainfall event；最大 event `RAIN_053` 被用 diamond 高亮，图上标注 `238.6 mm, 11 days`。图内说明大约 77–79% events 的 `Delta Q` 低于 0.05 mm。

**怎么计算。** `scripts/10_prepare_weather.py` 把 ARPA-style hourly precipitation 聚合成 daily，并用 `rain day > 1.0 mm`、`one dry day gap` 分割出 2019–2020 年 92 个 `rainfall events`。`scripts/11_run_simplified_runoff.py` 对每个 event 分别计算 `baseline` 和 `burned` 的 SCS-CN runoff。`scripts/figures/fig04_event_rainfall_response.py` merge `post_fire_rainfall_events.csv` 和 `runoff_delta_by_event.csv`，画 `total_precip_mm` vs `delta_runoff_mm`。

**为什么存在。** 它说明 local model 是 event-based，不是 annual total。它也显示较大 rainfall event 通常产生较大的 `Delta Q`，最大 ΔQ 出现在 `RAIN_053`。

**说明的问题。** 最大 conservative ΔQ 是 0.281785 mm，约 3,696 m³；但 median ΔQ 约 0.000888 mm，很多 event 几乎没有 burn-related change。这防止只拿最大值过度概括。

**Feynman 一句话。** “每个点是一场雨；雨越大，模型有机会产生更大的 burned-minus-baseline runoff difference，但大多数小雨几乎不变。”

**不要这样讲。** 不要说这是 observed hydrograph；图里是 modelled response, not observed discharge。

### `latex/fig05_burn_footprint_area.png` — Burned-footprint scenario area hierarchy

![Bar chart of burned area inside model domain for three footprint scenarios](../latex/fig05_burn_footprint_area.png)

**图上是什么。** 三条 horizontal bars 比较三种 `burned footprint` definition：`Conservative dNBR` 23.8 ha，`Relaxed dNBR` 55.4 ha，`Official perimeter upper bound` 约 280.8 ha。

**怎么计算。** `scripts/18_burn_severity_ensemble.py` 读取 NBR / dNBR / burn class raster，重算 `dNBR = pre - post` 并用两套 thresholds 分类：current `DNBR_THRESHOLDS = (0.10, 0.27, 0.66)` 和 `RELAXED_THRESHOLDS = (0.05, 0.15, 0.40)`。`official_fire_perimeter_upper_bound` 则把 catchment 内 official fire overlap 作为 upper-bound footprint，并作为 moderate class sensitivity。

**为什么存在。** 它把最大的 uncertainty 可视化：我们到底把多少 area 定义为 burned？

**说明的问题。** Footprint 从 23.80 ha 到 280.76 ha，差了一个数量级。这比很多模型参数扰动更能改变 local runoff conclusion。

**Feynman 一句话。** “这张图问的是：如果我们改变‘哪里算 burned’这个定义，模型需要调整的面积会变多少？”

**不要这样讲。** 不要说 upper bound 是 field truth；它只是 bounded sensitivity assumption。

### `latex/fig06_burn_runoff_response.png` — Maximum runoff response by burned-footprint scenario

![Bar chart of maximum modelled event Delta Q by burned-footprint scenario](../latex/fig06_burn_runoff_response.png)

**图上是什么。** 这张图与 `fig05` 对应，但横轴换成 `Maximum modelled event ΔQ (mm)`。结果大致是 `Conservative dNBR` 0.282 mm、`Relaxed dNBR` 0.69 mm、`Official perimeter upper bound` 5.5 mm。

**怎么计算。** 数据来自 `outputs/tables/burn_severity_ensemble_summary.csv`。`scripts/figures/fig06_burn_runoff_response.py` 读取每个 scenario 的 `max_runoff_delta_mm` 并绘制 bar chart。Upper-bound 的 5.505 mm 来自 `fire_perimeter_all_burned` sensitivity；conservative dNBR 的主模型最大值来自 `RAIN_053`。

**为什么存在。** `fig05` 只说明 area 不确定；`fig06` 说明 area 不确定会传导到 model output。它连接 `burn footprint` 和 `runoff response`。

**说明的问题。** Local runoff response 小，不一定是因为 fire 不重要，而是当前 conservative dNBR footprint 很小。扩大 footprint assumption 后，max ΔQ 会明显增大。

**Feynman 一句话。** “这张图把 footprint uncertainty 翻译成 runoff uncertainty。”

**不要这样讲。** 不要把 upper-bound 5.505 mm 当作最可能结果；它是 sensitivity 上限。

### `latex/fig07_event_delta_cdf.png` — Empirical CDF of event-scale ΔQ

![Empirical CDF of event-scale Delta Q with sensitivity markers](../latex/fig07_event_delta_cdf.png)

**图上是什么。** 横轴是 `Event ΔQ (mm)`，纵轴是 `Cumulative fraction`。蓝色曲线是 92 个 conservative dNBR event 的 empirical CDF，竖线标出 conservative max、relaxed max 和 upper-bound max。

**怎么计算。** `scripts/figures/fig07_event_delta_cdf.py` 读取 `runoff_delta_by_event.csv`，把 `delta_runoff_mm` 排序后用 `cdf = 1..n / n` 计算 cumulative fraction。然后从 `burn_severity_ensemble_summary.csv` 读取 relaxed 和 upper-bound 的 max ΔQ 作为竖线。

**为什么存在。** 它防止 audience 只盯着 maximum。最大值只是一个 event；CDF 告诉你整个 event distribution 是什么样。

**说明的问题。** 大多数 conservative event ΔQ 很小，约 79% events 小于 0.05 mm；但 upper-bound scenario 说明如果 footprint assumption 改变，最大可能响应会到 5.505 mm。

**Feynman 一句话。** “这张图告诉你：最大值不是常态，大多数雨事件的 modeled change 很小。”

**不要这样讲。** 不要说 CDF 曲线代表 rainfall probability 或 return period；它只是当前 92 个 observed events 的 empirical distribution。

### `latex/fig08_sensitivity_hierarchy.png` — Sensitivity hierarchy

![Tornado-style sensitivity hierarchy showing ranges for major uncertainty sources](../latex/fig08_sensitivity_hierarchy.png)

**图上是什么。** 这是一个 tornado / range plot，比对五类 local numeric sensitivity：`Burned footprint`、`Burn index`、`Rainfall station/IDW`、`Initial abstraction`、`Soil/HSG-CN`。横轴是 `Max modelled runoff-potential ΔQ (mm)`。

**怎么计算。** `scripts/figures/fig08_sensitivity_hierarchy.py` 从多个表读取 min–max range：`burn_severity_ensemble_summary.csv` 给 burned footprint range，`burn_index_sensitivity_summary.csv` 给 dNBR / RdNBR / RBR index sensitivity，`rainfall_station_sensitivity.csv` 给 station / IDW rainfall sensitivity，`scs_initial_abstraction_sensitivity.csv` 给 λ=0.20 vs λ=0.05，`soil_hsg_ensemble_summary.csv` 给 HSG/CN sensitivity。

**为什么存在。** 它回答“最值得下一步改进的 uncertainty 是什么？”不是每个 uncertainty 都同等重要。

**说明的问题。** `Burned footprint` 的 range 最大，约 0.282–5.505 mm；`Burn index` 次之；rainfall station、initial abstraction、soil/HSG-CN 在当前 conservative setting 下 range 相对小。Spatial boundary / outlet uncertainty 很重要，但在本图中不作为 numeric bar，而是通过 catchment/fire/outlet validation maps 和 tables 单独解释。

**Feynman 一句话。** “这张图像优先级清单：如果只能改进一个地方，先改进 burned footprint evidence。”

**不要这样讲。** 不要说 soil 或 rainfall 不重要；只是在当前 sensitivity setup 里，它们对 max ΔQ 的范围小于 footprint definition。

### `latex/fig09_weppcloud_sediment.png` — WEPPcloud sediment discharge comparison

![WEPPcloud sediment discharge comparison between undisturbed baseline and burned scenario](../latex/fig09_weppcloud_sediment.png)

**图上是什么。** 两根 bar 比较 `Undisturbed Baseline` 和 `Burned Scenario` 的 WEPPcloud `Sediment discharge (tonne/yr)`：293 和 653，标注 `+122.7%`。

**怎么计算。** `scripts/figures/fig09_weppcloud_sediment.py` 使用 WEPPcloud disturbed / undisturbed outlet summary 中的 sediment discharge 值：293.0 和 652.6 tonne/yr。详细解释来自 `outputs/models/weppcloud/WEPPcloud_vs_SCS_CN_COMPARISON.md`。

**为什么存在。** Local SCS-CN 不计算 sediment。WEPPcloud 的作用是提供 process-model benchmark，尤其是 hillslope erosion / sediment delivery 的方向。

**说明的问题。** WEPPcloud 的主要 fire signal 是 sediment：sediment discharge 增加 122.7%，hillslope soil loss 也大幅增加；但 stream discharge 只是 2,124 → 2,125 mm/yr，几乎不变。因此不能说 WEPPcloud 证明 local runoff increase。

**Feynman 一句话。** “Local model 看 event runoff；WEPPcloud 告诉我们火后更明显的风险可能是 sediment delivery。”

**不要这样讲。** 不要说 sediment discharge 是 field-measured erosion；它是 uncalibrated WEPPcloud screening estimate，也不是 local SCS-CN 的 validation。

---

## 🔍 Validation and supporting maps

### `outputs/maps/00_fire_perimeter_check.png` — Fire perimeter check

![Fire perimeter check map with official fire, processing AOI, hydrography, and Lake Varese](../outputs/maps/00_fire_perimeter_check.png)

**图上是什么。** 这张 validation map 显示 `Official 2019 fire`、`Processing AOI`、hydrography 和 Lake Varese。

**怎么计算。** `scripts/04_prepare_spatial_frame.py` 从 local official Regione Lombardia fire perimeter archive 中筛选 2019 年、与 AOI 相交、Monte Martica / Varese 属性匹配的 polygon，并保存候选表 `qa/evidence/fire_perimeter_candidates.csv`。

**为什么存在。** 它证明 fire reference 不是手画的模型假设，而是从 official source data 中 deterministic selection 得来。

**说明的问题。** Fire perimeter 是 official reference，但它只是 burned area reference；它不自动等于 dNBR burned proxy，也不自动等于 selected outlet 的 catchment。

**Feynman 一句话。** “这张图回答：我们说的 official fire perimeter 到底是哪一个 polygon？”

### `outputs/maps/01_processing_aoi_not_final_boundary.png` — Processing AOI context

![Processing AOI context map indicating the AOI is not the final catchment boundary](../outputs/maps/01_processing_aoi_not_final_boundary.png)

**图上是什么。** 这张图显示 processing AOI、Lake Varese 和 hydrography，标题明确写着 `Processing mask only — not a final catchment boundary`。

**怎么计算。** 同样来自 `scripts/04_prepare_spatial_frame.py`，AOI 由 project-owner supplied AOI 或 fallback AOI 生成，属性中标为 `processing_mask_only` 和 `scientific_boundary=false`。

**为什么存在。** 很多错误解释来自把 AOI box 当成 model boundary。这张图专门防止这种误解。

**说明的问题。** AOI 是数据读取 / clipping window，不是 hydrologic catchment，不应用来报告面积、runoff 或 fire overlap conclusion。

**Feynman 一句话。** “AOI 是取数据的窗口，不是水流汇集的盆。”

### `outputs/maps/03_final_catchment_fire_hydrography_overlay.png` — Catchment and hydrology check

![Catchment and hydrology check map for the candidate catchment, fire, outlet, and streams](../outputs/maps/03_final_catchment_fire_hydrography_overlay.png)

**图上是什么。** 这张 supporting map 显示 `Catchment candidate`、Lake Varese、`Processing AOI`、`DEM streams`、`Official 2019 fire` 和 `Outlet candidate`。

**怎么计算。** 它由 `scripts/05_prepare_dem.py` 在生成 DEM hydrology derivatives 后输出。Catchment 来自 Whitebox D8 watershed 或 fallback constrained polygon；outlet 来自 flow accumulation / elevation score。

**为什么存在。** 它是 local boundary 的主 validation 图，也被复制到 WEPPcloud input package 作为 manual upload reference。

**说明的问题。** 当前 catchment 面积 1,311.76 ha；official fire inside current catchment 为 280.14 ha，但 fire outside current catchment 为 96.11 ha。图上可直观看到 one outlet 不覆盖 whole official fire。

**Feynman 一句话。** “这张图是 local model 的地理底盘。”

### `outputs/maps/06_burn_severity_proxy_vs_fire_reference.png` — Burn-severity proxy vs official fire reference

![Burn-severity proxy map compared with official fire reference](../outputs/maps/06_burn_severity_proxy_vs_fire_reference.png)

**图上是什么。** 这张 map 把 `burn_severity_proxy` categorical raster 与 catchment boundary、official fire reference 叠加。颜色代表 Unburned / Low / Moderate / High / NoData。

**怎么计算。** `scripts/07_prepare_burn_severity.py` 读取 Sentinel-2 pre/post SAFE ZIP，计算 `NBR` 和 `dNBR`，按 thresholds 分类成 `uint8` raster。Class summary 显示 valid pixels 中 unburned 385.40 ha、low 18.60 ha、moderate 5.20 ha、high 0.00 ha，NoData 2,325.84 ha。

**为什么存在。** 它解释为什么 conservative local runoff response 小：dNBR proxy 在 official fire perimeter 内只识别出很小的 positive burn area。

**说明的问题。** Large NoData / limited valid dNBR coverage 是关键 uncertainty。NoData `255` 不是 high severity，也不能当 burned。

**Feynman 一句话。** “这张图说明 satellite proxy 只在一小部分 catchment 里给出了 positive burn evidence。”

### `outputs/maps/07_runoff_delta_event_main.png` — Runoff response units

![Runoff response units map showing SCS-CN curve-number adjustment](../outputs/maps/07_runoff_delta_event_main.png)

**图上是什么。** 图中颜色表示 `CN adjustment (dimensionless)`，catchment outline 标出 candidate boundary。它与 `latex/fig03_response_units_map.png` 类似，但是 pipeline QGIS-like output。

**怎么计算。** `scripts/11_run_simplified_runoff.py` 在完成 92 events × 4 scenarios 的 local SCS-CN calculation 后，将每个 response unit 的 `burned_parameter - baseline_parameter` 写成 map。

**为什么存在。** 它把 table outputs 转成 spatial validation：到底哪些 response units 的 CN 被调整，调整幅度是多少。

**说明的问题。** High ΔCN areas 很少且集中，说明 output sensitivity 受 burned footprint 强烈控制。

**Feynman 一句话。** “如果 `fig04_event_rainfall_response` 是最终跑分，这张图就是跑分前每块地的参数变化。”

### `outputs/maps/08_quantitative_spatial_qa.png` — Quantitative spatial validation context

![Quantitative spatial validation context map with catchment, fire, outlet, and streams](../outputs/maps/08_quantitative_spatial_qa.png)

**图上是什么。** 图中叠加 local catchment、official fire perimeter、selected outlet、official hydrography 和 DEM D8 streams。

**怎么计算。** `scripts/14_quantitative_spatial_qa.py` 先写出 numeric validation tables，然后用 `make_context_map()` 输出这张 map。关键 numeric decision 写入 `qa/spatial/quantitative_spatial_qa_summary.json` 和 `qa/spatial/qa_decisions.csv`。

**为什么存在。** 它是 numeric validation 的 visual companion。Caption 明确说明：acceptance 依据是 CSV/JSON metrics，不是视觉判断。

**说明的问题。** Overall decision 是 `WARN`：`fire_inside_current_catchment` 为 WARN，`soil_resolution` 为 WARN；`hydrology_grid_alignment`、`burn_raster_domain`、`outlet_flow_accumulation` 为 PASS。

**Feynman 一句话。** “这张图只是 validation 的地图索引，真正的判定在表格里。”

### `outputs/figures/burn_severity_ensemble_map.png` — Burn-footprint ensemble map

![Burn-footprint ensemble map comparing conservative dNBR, relaxed dNBR, and official perimeter upper bound](../outputs/figures/burn_severity_ensemble_map.png)

**图上是什么。** 三个 panel 比较 `A Conservative dNBR proxy`、`B Relaxed dNBR proxy`、`C Official perimeter upper bound`。黑线是 catchment，红色虚线是 official fire。

**怎么计算。** `scripts/18_burn_severity_ensemble.py` 使用同一 NBR/dNBR grid 重新分类：conservative thresholds 为 0.10 / 0.27 / 0.66，relaxed thresholds 为 0.05 / 0.15 / 0.40，upper bound 把 catchment 内 official fire area 设为 moderate burn class。

**为什么存在。** 它把 `fig05` 的 area ladder 放回空间中，让你看到三种 footprint assumption 不只是数字不同，空间 coverage 也不同。

**说明的问题。** Conservative proxy 是 lower proxy；relaxed proxy 是 threshold sensitivity；official perimeter 是 upper-bound assumption。它们都不是 field soil burn severity。

**Feynman 一句话。** “这张图把‘不同 burned definition’画成三张地图，让你看到 uncertainty 是空间上的。”

### `outputs/figures/burned_area_uncertainty_ladder.png` — Combined burned area and runoff response ladder

![Combined figure with burned footprint area hierarchy and propagated event-runoff response](../outputs/figures/burned_area_uncertainty_ladder.png)

**图上是什么。** 这是两 panel figure：A 是 `Burned-footprint scenario hierarchy`，B 是 `Propagated event-runoff response`。

**怎么计算。** 它与 `latex/fig05_burn_footprint_area.png` 和 `latex/fig06_burn_runoff_response.png` 使用同一类数据：`burn_severity_ensemble_summary.csv`。左边画 `burned_area_ha`，右边画 `max_runoff_delta_mm`。

**为什么存在。** 它把“area uncertainty”和“runoff uncertainty”放在同一张图里，适合在一页 result slide 上讲清楚 footprint propagation。

**说明的问题。** 只要 footprint 从 conservative dNBR 变到 official perimeter upper bound，输出 ΔQ 就从小量级变成 5.5 mm 量级。

**Feynman 一句话。** “左边是原因的大小，右边是结果的大小。”

### `outputs/figures/final_fig02_burn_uncertainty.png` — Final burn uncertainty composite

![Final burn uncertainty composite figure](../outputs/figures/final_fig02_burn_uncertainty.png)

**图上是什么。** 这也是一个 `burn footprint` 与 `maximum modelled runoff-potential delta` 的 composite figure，视觉上更适合最终报告版式。

**怎么计算。** 与 `burned_area_uncertainty_ladder.png` 的 calculation 逻辑相同，只是 styling / final layout 不同。

**为什么存在。** 它可以作为 cleaned-up final figure，用于说明 uncertainty hierarchy，而不必分别展示 `fig05` 和 `fig06`。

**说明的问题。** 它再次强调：当前 conclusion 的主控因素是 burned footprint definition。

**Feynman 一句话。** “这是 `fig05` 和 `fig06` 的合并讲法：footprint 越大，runoff-potential delta 上限越大。”

### WEPPcloud input package screenshots

这些文件位于 `../outputs/models/weppcloud/input_package/screenshots_for_upload_reference/`。它们不是新的 scientific results，而是 manual WEPPcloud operation 的 reference copies。

| Screenshot | 作用 | 怎么讲 |
| --- | --- | --- |
| `03_final_catchment_fire_hydrography_overlay.png` | 复制 local catchment / fire / outlet / hydrography reference | 用于在 WEPPcloud 中核对 outlet 和 watershed context |
| `06_burn_severity_proxy_vs_fire_reference.png` | 复制 burn severity proxy reference | 用于确认 uploaded burn raster 的 class meaning 和 NoData |
| `07_runoff_delta_event_main.png` | 复制 response units / CN adjustment reference | 用于解释 local model 与 WEPPcloud 的 burn raster relation |
| `rainfall_events_2019.png` | top rainfall event bar chart | 用于说明 local observed rainfall forcing，不是 WEPPcloud climate |
| `weppcloud_input_package_overview.png` | WEPPcloud package overview table | 用于记录 zip package、catchment reference、official fire reference、outlet、burn raster、local runoff table 和 manual WEPPcloud status |

Feynman 解释：这些 screenshots 像“上传说明书里的配图”。它们帮助你在 WEPPcloud webpage 操作时不把 outlet、burn raster、reference layers 搞混，但它们本身不产生新的 model result。

---

## 📊 Figure crosswalk

| 如果你要讲的问题 | 首选 figure | 辅助 figure / table |
| --- | --- | --- |
| 研究区在哪里 | `fig01a_north_Italy.png` | `fig01c_local_domain.png` |
| Current local model domain 是什么 | `fig01c_local_domain.png` | `outputs/maps/03_final_catchment_fire_hydrography_overlay.png`, `qa/spatial/fire_catchment_overlap.csv` |
| Outlet 是否 hydrologically plausible | `fig02_dem_hydrology_qa.png` | `qa/spatial/outlet_plausibility.csv`, `outputs/maps/08_quantitative_spatial_qa.png` |
| dNBR proxy 为什么小 | `outputs/maps/06_burn_severity_proxy_vs_fire_reference.png` | `outputs/tables/burn_severity_area_summary.csv` |
| SCS-CN 如何从 GIS 变成 model units | `fig03_response_units_map.png` | `fig04_response_unit_cn_adjustment.png`, `outputs/tables/runoff_units.csv` |
| Rainfall event 和 ΔQ 的关系 | `fig04_event_rainfall_response.png` | `outputs/tables/runoff_delta_by_event.csv` |
| 为什么最大 ΔQ 不能代表所有 events | `fig07_event_delta_cdf.png` | `outputs/tables/runoff_delta_by_event.csv` |
| 主要 uncertainty 是什么 | `fig08_sensitivity_hierarchy.png` | `burned_area_uncertainty_ladder.png` |
| Burn footprint 如何控制 runoff response | `fig05_burn_footprint_area.png` + `fig06_burn_runoff_response.png` | `final_fig02_burn_uncertainty.png` |
| WEPPcloud benchmark 的核心 message | `fig09_weppcloud_sediment.png` | `outputs/models/weppcloud/WEPPcloud_vs_SCS_CN_COMPARISON.md` |

---

## 🔄 Runoff 和 WEPPcloud 目前怎么相互呼应

先给最短答案：**WEPPcloud 不是没有 runoff / water result；它有 `Stream discharge`、land-use-level `Avg Runoff Depth`、daily streamflow / water balance outputs。问题是：这些不是 local SCS-CN 的 `event-scale burned - baseline direct runoff ΔQ`，所以不能把两个 runoff 数字直接相减或说互相验证。**

### WEPPcloud 到底有没有 runoff result

有，但它回答的是 WEPPcloud 自己的 continuous water-balance 问题。

| WEPPcloud output | 当前结果 | 它代表什么 | 能不能和 local ΔQ 直接比较 |
| --- | ---: | --- | --- |
| `Stream discharge` at outlet | Undisturbed 2,124 mm/yr → Disturbed 2,125 mm/yr | WEPPcloud watershed outlet 的 annual stream discharge / water yield | 不能直接比较；这是 annual continuous output，不是 event direct runoff |
| `Avg Runoff Depth` by land use | Broad-leaved forest 306–314 mm/yr；Low Severity Fire 234 mm/yr；urban 2,121 mm/yr | WEPPcloud landuse class 的 average annual runoff depth | 不能直接当作 catchment-level fire runoff effect；landuse parameterization 有差异 |
| Daily streamflow / `totalwatsed3.csv` | 100-year daily simulation | Continuous simulation 的 daily water / sediment time series | 只有在重新抽取同类 event windows 后才可能做间接 comparison |
| `Sediment discharge` | 293.0 → 652.6 tonne/yr, +122.7% | WEPPcloud 最清楚的 disturbed-vs-undisturbed signal | 可以作为 sediment / erosion benchmark，但不是 runoff validation |

所以如果你问“WEPPcloud 有没有给我一个和 local SCS-CN 一样的 runoff answer？”答案是：**没有同口径的 answer**。如果你问“WEPPcloud 有没有 hydrology / water-balance output？”答案是：**有，而且它显示 annual `Stream discharge` 基本不变。**

### Local runoff result 是什么

Local model 的 result 是：在 current selected outlet 和 current conservative dNBR footprint 下，对 2019–2020 年 92 个 observed `rainfall events`，用 simplified `SCS-CN` 分别计算 `baseline` 和 `burned scenario`，然后看：

```text
local runoff result = burned scenario direct runoff Q - baseline direct runoff Q
```

当前核心值是：

| Local SCS-CN item | 当前值 | 解释 |
| --- | ---: | --- |
| Events modelled | 92 | 2019–2020 observed rainfall events |
| Conservative burned proxy | 23.80 ha | dNBR positive burn classes，占 catchment 1.8% |
| Max event ΔQ | 0.281785 mm | `RAIN_053` 的 `burned - baseline` direct runoff depth |
| Max event ΔQ volume | 3,696 m³ | 同一 event 的 volume difference |
| Upper-bound footprint ΔQ | 5.505 mm | 如果用 official fire perimeter upper-bound footprint，max ΔQ 会明显变大 |

这回答的是：**在同一场 observed rainfall event 下，如果只改变 burn-related CN，direct runoff estimate 会变多少？**

### WEPPcloud result 是什么

WEPPcloud result 是：在 WEPPcloud 自己 delineated 的 1,073.66 ha watershed 里，比较 undisturbed 和 disturbed scenario 的 continuous water balance / sediment output。

| WEPPcloud item | Undisturbed | Disturbed | 解释 |
| --- | ---: | ---: | --- |
| Watershed area | 1,073.66 ha | 1,073.66 ha | 两个 WEPPcloud scenarios 内部一致 |
| Precipitation | 2,872 mm/yr | 2,872 mm/yr | 同一 WEPPcloud climate forcing |
| Stream discharge | 2,124 mm/yr | 2,125 mm/yr | runoff / water-yield signal 很弱，几乎不变 |
| Hillslope soil loss | 431.3 tonne/yr | 1,157.1 tonne/yr | disturbed hillslope erosion 明显增加 |
| Sediment discharge | 293.0 tonne/yr | 652.6 tonne/yr | sediment signal +122.7% |
| Disturbed burned landuse | n/a | 175.7 ha `Low Severity Fire` | 比 local conservative 23.8 ha 大很多 |

这回答的是：**在 WEPPcloud process model 中，disturbed land use / soil parameters 对 annual water balance 和 sediment delivery 有什么影响？**

### 两者为什么不能直接对 runoff 数字

| Difference | Local SCS-CN | WEPPcloud | 影响 |
| --- | --- | --- | --- |
| Time basis | 2019–2020 observed event model | 100-year continuous climate / annual summaries | `mm/event` 不能直接和 `mm/yr` 比 |
| Runoff definition | `direct runoff Q` / precipitation excess | `Stream discharge`, landuse `Avg Runoff Depth`, baseflow / lateral flow / runoff components | 变量结构不同 |
| Watershed | 1,311.76 ha local DEM-derived catchment | 1,073.66 ha WEPPcloud watershed | 面积差 18.2%，不能一对一 |
| Burned area | 23.80 ha conservative dNBR proxy | 175.7 ha `Low Severity Fire` landuse | disturbed footprint 不同，signal size 当然不同 |
| Model physics | Simplified SCS-CN, no sediment | WEPP / WEPPcloud, includes erosion and sediment | WEPPcloud 能回答 sediment，local SCS-CN 不能 |

最重要的是：local `runoff_total_mm` 是 event direct runoff depth；WEPPcloud `Stream discharge` 是 continuous model 的 annual outlet water yield。它们都含有“水从 catchment 出去”的意思，但不是同一种 measurement。

### 目前正确的“相互呼应”方式

当前不是“两个模型给出同一个 runoff number”，而是下面这种三层呼应：

1. **Runoff-volume signal 都不是最强结论。**  
   Local conservative SCS-CN 的 max ΔQ 只有 0.281785 mm；WEPPcloud annual stream discharge 只从 2,124 到 2,125 mm/yr。两者共同支持：不要把当前研究讲成“已经证明 runoff 大幅增加”。

2. **Burn footprint controls the local runoff signal。**  
   Local result 显示 conservative 23.80 ha footprint 给小 ΔQ；upper-bound 280.76 ha footprint 可给 5.505 mm。这解释了为什么 WEPPcloud 使用 175.7 ha disturbed landuse 时，不能期待和 local 23.8 ha conservative dNBR 得到同样大小的 response。

3. **WEPPcloud 的主要补充价值是 sediment / erosion。**  
   WEPPcloud 的 runoff / stream discharge 变化很小，但 sediment discharge 增加 122.7%。这和 local SCS-CN 形成互补：local model 只能做 event direct runoff screening；WEPPcloud 告诉我们 process-model 中 fire disturbance 更明显地体现在 hillslope erosion / sediment delivery。

### 汇报时推荐这样讲

可以说：

> The local SCS-CN model provides event-scale direct-runoff sensitivity under observed 2019–2020 rainfall. Under the conservative dNBR footprint, the maximum burned-minus-baseline runoff change is small, 0.282 mm, because only 23.8 ha of the catchment receives burn-related CN adjustment. WEPPcloud does provide hydrologic outputs, but its comparable annual stream-discharge signal is also small, 2,124 to 2,125 mm/yr. The stronger WEPPcloud fire signal is sediment discharge, 293.0 to 652.6 tonne/yr. Therefore, the two models should be interpreted as complementary: local SCS-CN screens event runoff sensitivity, while WEPPcloud highlights sediment / erosion response and water-balance context.

中文 Feynman 版本：

> 我的 local model 像是在问：“同一场雨下，烧过以后 direct runoff 会多多少？”WEPPcloud 像是在问：“长期气候和过程模型里，水量和泥沙输出怎么变？”现在两个模型都没有给出强 runoff-volume increase 的证据；它们真正呼应的是：runoff 结果很依赖 burned footprint，而 WEPPcloud 显示更强的 fire signal 在 sediment，不在 annual stream discharge。

### 不建议这样讲

| 不建议说法 | 为什么不对 | 推荐替代 |
| --- | --- | --- |
| “WEPPcloud 没有 runoff result” | 它有 `Stream discharge` 和 `Avg Runoff Depth`，只是不同口径 | “WEPPcloud 没有与 local event ΔQ 同口径的 runoff answer。” |
| “WEPPcloud validates my SCS-CN runoff” | 时间、面积、burned footprint、model physics 都不同 | “WEPPcloud is an independent process-model benchmark, not validation.” |
| “Fire caused runoff increase of X%” | 没有 observed discharge validation，WEPPcloud stream discharge 几乎不变 | “Local model estimates screening-level event runoff-potential change.” |
| “Sediment result proves runoff result” | Sediment 和 runoff 是不同 process outputs | “Sediment response suggests erosion risk, which local SCS-CN cannot simulate.” |

---

## ⚠️ Issues each figure set illustrates

### Boundary issue: `AOI`、`catchment`、`fire perimeter`、`WEPPcloud watershed` 不一样

`AOI` 是 processing mask；`catchment` 是 selected outlet 的 upstream area；`official fire perimeter` 是火场 reference；`WEPPcloud watershed` 是 WEPPcloud internal DEM / channel network / snapped outlet 生成的 watershed。它们不应该互相替代。当前 local catchment 是 1,311.76 ha，WEPPcloud watershed 是 1,073.66 ha，差异约 18.2%。

### Burn footprint issue: 最大的不确定性来自“哪里算 burned”

Conservative dNBR 只有 23.80 ha；relaxed dNBR 是 55.36 ha；official perimeter upper bound 是 280.76 ha。同一个 SCS-CN framework 中，只改变 footprint，max ΔQ 就从 0.282 mm 变到 5.505 mm。

### Proxy issue: `dNBR` 不是 `field soil burn severity`

Sentinel-2 dNBR 反映 spectral / vegetation response。它受 cloud / SCL masking、pre/post scene selection、thresholds 和 terrain/shadow 影响。报告里必须说 `remote-sensing burn-severity proxy`。

### Model issue: Local SCS-CN 和 WEPPcloud 回答不同问题

Local SCS-CN 回答 observed 2019–2020 rainfall events 下，CN adjustment 可能让 event direct runoff 改变多少。WEPPcloud 回答 process-based continuous simulation 下 annual water balance、hillslope erosion、channel soil loss 和 sediment discharge 如何变化。它们是 complementary screening tools，不是 mutual validation。

### Validation issue: 当前结果是 usable baseline，但 overall `WARN`

Structural raster/grid checks 和 burn raster domain 是 PASS；outlet flow accumulation 是 PASS；但 fire perimeter 不是完全落在当前 catchment 内，SoilGrids-derived HSG 相对 DEM 粗。因此当前结果可用于 selected outlet baseline screening，不可用于 whole-fire calibrated claim。

---

## ✍️ Feynman self-test

1. **如果别人问：“为什么 local runoff increase 这么小？”**

   回答：因为 conservative dNBR burned proxy 只有 23.80 ha，占 catchment 1.8%；SCS-CN 只在 positive burn classes 的 response units 上做 CN adjustment。图上用 `fig03`、`fig04_response_unit_cn_adjustment`、`fig05` 和 `fig06` 连起来解释。

2. **如果别人问：“Official fire perimeter 是 376 ha，为什么你只用了 23.8 ha？”**

   回答：376 ha 是 official fire reference；23.8 ha 是 Sentinel-2 conservative dNBR proxy 在当前 catchment 中的 positive burned classes。它们代表不同证据。为了不把 proxy 当真值，项目又做了 relaxed dNBR 和 official perimeter upper-bound sensitivity。

3. **如果别人问：“WEPPcloud 证明你的 local SCS-CN 对吗？”**

   回答：不能这样说。WEPPcloud 的 watershed、climate、soil、landuse、time basis 和 model physics 都不同。它提供 independent process-model benchmark，尤其显示 sediment discharge 增加 122.7%，但不是 local runoff number 的 validation。

4. **如果别人问：“你有没有观测到 post-fire runoff increase？”**

   回答：没有。当前没有 selected outlet 的 observed discharge / sediment / turbidity / chlorophyll-a validation。所有 local runoff values 都是 screening-level, uncalibrated model estimates。

5. **如果别人问：“下一步最该改哪里？”**

   回答：先改 burned footprint evidence 和 multi-outlet / catchment partitioning。`fig08_sensitivity_hierarchy.png` 显示 burned footprint 是 local runoff uncertainty 的最大来源；validation records 也显示当前 one outlet 不代表 whole official fire。

---

## 🔗 Internal evidence sources

| Evidence | Path |
| --- | --- |
| Figure orchestrator | `scripts/figures/run_all_atomic_figures.py` |
| Figure style and I/O | `scripts/figures/lib/figure_style.py`, `scripts/figures/lib/io.py` |
| Spatial frame and AOI/fire maps | `scripts/04_prepare_spatial_frame.py` |
| DEM / D8 hydrology / catchment / outlet | `scripts/05_prepare_dem.py` |
| Sentinel-2 NBR / dNBR / burn classes | `scripts/07_prepare_burn_severity.py` |
| Weather event extraction | `scripts/10_prepare_weather.py` |
| SCS-CN response units and runoff events | `scripts/11_run_simplified_runoff.py` |
| Burn-footprint ensemble | `scripts/18_burn_severity_ensemble.py` |
| Quantitative spatial validation | `scripts/14_quantitative_spatial_qa.py` |
| Core project summary | `docs/PROJECT_SUMMARY.md`, `docs/PROJECT_CN.md` |
| WEPPcloud comparison | `outputs/models/weppcloud/WEPPcloud_vs_SCS_CN_COMPARISON.md` |
| Main numeric outputs | `outputs/tables/*.csv`, `qa/spatial/*.csv`, `qa/spatial/quantitative_spatial_qa_summary.json` |

## 🌊 Lake water-quality linkage figures

Lake WQ linkage figures now use the Python-only module under `scripts/lake_wq/figures/`. They connect runoff screening to lake-side remote-sensing proxy response, but numeric anomaly interpretation is allowed only when local Sentinel-2 pre/post event pairs exist.

| Figure | Output | Meaning | Current status |
|---|---|---|---|
| `fig10_runoff_vs_lake_turbidity_proxy.png` | `latex/fig10_runoff_vs_lake_turbidity_proxy.png` | `delta_volume_m3` or `delta_runoff_mm` vs `delta_ndti_mean`, grouped by ROI | Placeholder-limited: current local SAFE archive lacks selected-event pre/post NDTI pairs |
| `fig11_runoff_vs_lake_chla_proxy.png` | `latex/fig11_runoff_vs_lake_chla_proxy.png` | runoff potential vs `delta_ndci_mean`, grouped by ROI | Placeholder-limited: current local SAFE archive lacks selected-event pre/post NDCI pairs |
| `fig12_lake_water_quality_event_panel.png` | `latex/fig12_lake_water_quality_event_panel.png` | strongest available event pre/post/delta NDTI or NDCI map | Placeholder-limited: no local Sentinel-2 pre/post event pair exists in current raw archive |
| `fig13_runoff_to_lake_wq_closure.png` | `latex/fig13_runoff_to_lake_wq_closure.png` | closure workflow: fire severity / CN adjustment → event runoff ΔQ/ΔV → sediment/runoff risk → Sentinel-2 proxy anomaly → ARPA context | Available; marks lake WQ proxy as data-limited when validation records have `MISSING_LOCAL_IMAGE` |

**怎么解释。** The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes. NDTI 是 primary lake-side response，因为它更接近 suspended sediment / turbidity。NDCI 是 secondary and indirect，因为 chlorophyll-a 还受 nutrients、light、temperature、mixing、stratification、biological lag 控制。

**当前限制。** 本地 SAFE archive 只有 2018-12 / 2019-01 Sentinel-2 scenes，不覆盖 selected high-runoff events；因此 fig10–fig12 是清楚说明 data gap 的 placeholder，而不是空缺或 GEE fallback。

**不要这样讲。** 不要说 “Runoff predicts chlorophyll-a.” 不要说 active workflow 使用 GEE。不要做 calibrated water-quality prediction、runoff-to-lake causality、measured runoff increase、或 “model proves post-fire lake impact” claims。
