# 中文项目摘要

本项目研究 Lake Varese / Monte Martica 2019 wildfire 后，burned catchments 的 post-fire runoff screening。当前 workflow 使用 EPSG:32632 做本地 metric processing，使用 DTM / WhiteboxTools D8 hydrology 划定 catchment/outlet，用 Sentinel-2 dNBR 生成 burn severity proxy，用 DUSAF6 2018 land cover 和 SoilGrids-derived HSG 生成 SCS-CN response units，并用 2019–2020 rainfall events 计算 baseline 与 burned scenario 的 event direct runoff difference。

---

## 当前核心事实

- Local catchment：1,311.76 ha。
- Official fire perimeter：376.25 ha。
- Fire inside current catchment：280.14 ha，74.5%。
- Conservative dNBR burned proxy：23.80 ha，占 catchment 1.8%。
- Fire-perimeter upper-bound：280.76 ha，占 21.4%。
- Local SCS-CN conservative 最大 runoff-potential change：0.282 mm，约 3,696 m³。
- Upper-bound 最大 runoff-potential change：5.505 mm，约 72,208 m³。
- WEPPcloud sediment discharge：293.0 → 652.6 tonne/yr，增加 122.7%。
- WEPPcloud stream discharge：2,124 → 2,125 mm/yr，几乎不变。

---

## 最重要的解释

当前 local runoff response 小，主要因为 conservative dNBR footprint 很小，不代表火灾一定没有 downstream impact。WEPPcloud 显示 sediment response 明显增加，说明 fire effect 可能更多体现在 erosion/sediment delivery，而不是 annual stream discharge。local SCS-CN 和 WEPPcloud 是 complementary screening evidence，不是相互 validation。

详细中文两小时讲稿见 `docs/PRESENTATION_DRAFT_CN_2H.md`。

## Lake water-quality linkage（水质遥感响应链条）

### Python-only lake water-quality closure

项目现在保留原有 SCS-CN runoff model 和 WEPPcloud benchmark，只把最后一段 lake-side proxy comparison 改成 Python-only workflow。核心句子是：**The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes.**

新增主目录是 `scripts/lake_wq/`。`scripts/16_select_lake_response_events.py` 和 `scripts/17_prepare_sentinel2_lake_water_quality.py` 现在只是 thin wrappers，真正 compute code 都在 `scripts/lake_wq/`，figure code 都在 `scripts/lake_wq/figures/`。

流程使用本地 `data/raw/zip/*.SAFE.zip` Sentinel-2 L2A，不使用 Google Earth Engine。指数定义为：

```text
NDTI = (B4 - B3) / (B4 + B3)
NDCI = (B5 - B4) / (B5 + B4)
```

NDTI 是 primary lake-side response，因为它更接近 suspended sediment / turbidity。NDCI 是 secondary and indirect，因为 chlorophyll-a 还受 nutrients、light、temperature、mixing、stratification、biological lag 影响。不能说 runoff predicts chlorophyll-a。

当前 selected events 是 `RAIN_053`, `RAIN_057`, `RAIN_083`, `RAIN_089`, `RAIN_082`, `RAIN_068`, `RAIN_046`, `RAIN_072`, `RAIN_013`, and `RAIN_067`，按 `delta_volume_m3` 排名。本地 Sentinel-2 SAFE 只覆盖 `2018-12-31` 到 `2019-01-15`，不能覆盖这些 selected events 的 pre/post windows，所以 validation record 写入 `MISSING_LOCAL_IMAGE`，作为 local data limitation，而不是用 GEE 补齐。

ARPA lake analytical data 只作为 context（chlorophyll-a、Secchi / transparency、phosphorus、oxygen、temperature 等），不做 runoff correlation、calibration 或 causal attribution。GEE is not used。
