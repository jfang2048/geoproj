"""Dynamic workflow diagrams rendered with Graphviz — no PNG images."""
from __future__ import annotations


def project_workflow() -> str:
    """Return a Graphviz DOT string for the main project workflow."""
    return """
    digraph workflow {
        rankdir=LR
        splines=polyline
        nodesep=0.5
        ranksep=0.9
        bgcolor="#ffffff"

        node [shape=box, style="filled,rounded", fontname="Inter,Segoe UI,sans-serif",
              fontsize=11, margin="0.18,0.14", penwidth=1.2]

        edge [color="#94a3b8", penwidth=1.1, arrowsize=0.7]

        subgraph cluster_inputs {
            label="Input data"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#f8fafc"
            penwidth=0.8

            dem    [label="DTM5 DEM"               fillcolor="#e0f2fe" color="#38bdf8"]
            fire   [label="Fire perimeter"          fillcolor="#e0f2fe" color="#38bdf8"]
            s2     [label="Sentinel-2 L2A"          fillcolor="#e0f2fe" color="#38bdf8"]
            lc     [label="DUSAF6 land cover"       fillcolor="#e0f2fe" color="#38bdf8"]
            soil   [label="SoilGrids HSG"           fillcolor="#e0f2fe" color="#38bdf8"]
            rain   [label="ARPA rainfall"           fillcolor="#e0f2fe" color="#38bdf8"]
        }

        subgraph cluster_processing {
            label="Processing"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#f8fafc"
            penwidth=0.8

            spatial  [label="Spatial frame\ncatchment + outlet" fillcolor="#dbeafe" color="#60a5fa"]
            dNBR     [label="Burn proxy\ndNBR classification"   fillcolor="#dbeafe" color="#60a5fa"]
            units    [label="Response units\nCN assignment"     fillcolor="#dbeafe" color="#60a5fa"]
        }

        subgraph cluster_models {
            label="Models"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#f8fafc"
            penwidth=0.8

            scs    [label="SCS-CN event runoff\nscreening model" fillcolor="#d1fae5" color="#34d399"]
            wepp   [label="WEPPcloud-EU\nprocess benchmark"     fillcolor="#fef3c7" color="#fbbf24"]
        }

        subgraph cluster_results {
            label="Results"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#f8fafc"
            penwidth=0.8

            dq      [label="Event runoff delta\nbaseline vs burned" fillcolor="#d1fae5" color="#34d399"]
            sed     [label="Sediment discharge\n+122.7%"            fillcolor="#fef3c7" color="#fbbf24"]
            lake_wq [label="Lake WQ closure\nPython-only"           fillcolor="#f1f5f9" color="#94a3b8"]
        }

        conclusion [label="Screening conclusion\nburned-footprint dominates uncertainty" shape=box
                    fillcolor="#ffffff" color="#64748b" style="filled,rounded"]

        # Edges
        dem -> spatial
        fire -> spatial
        s2 -> dNBR
        spatial -> dNBR
        dNBR -> units
        lc -> units
        soil -> units
        rain -> scs
        units -> scs
        scs -> dq
        units -> wepp
        dNBR -> wepp
        wepp -> sed
        dq -> lake_wq
        sed -> lake_wq
        dq -> conclusion
        sed -> conclusion
        lake_wq -> conclusion
    }
    """


def interpretation_flowchart() -> str:
    """Return a Graphviz DOT string showing model interpretation branches."""
    return """
    digraph interpretation {
        rankdir=TB
        splines=polyline
        nodesep=0.6
        ranksep=0.7
        bgcolor="#ffffff"

        node [shape=box, style="filled,rounded", fontname="Inter,Segoe UI,sans-serif",
              fontsize=10.5, margin="0.18,0.12", penwidth=1.1]

        edge [color="#94a3b8", penwidth=1.0, arrowsize=0.7]

        subgraph cluster_local {
            label="Local SCS-CN model"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#f0fdf4"
            penwidth=0.8
            color="#bbf7d0"

            local1 [label="Event-scale direct\nrunoff sensitivity"  fillcolor="#d1fae5" color="#34d399"]
            local2 [label="Burned minus baseline\ndelta Q"          fillcolor="#d1fae5" color="#34d399"]
            local3 [label="Conservative max delta Q\n0.282 mm"      fillcolor="#d1fae5" color="#34d399"]

            local1 -> local2 -> local3
        }

        subgraph cluster_wepp {
            label="WEPPcloud-EU benchmark"
            fontsize=10
            fontcolor="#64748b"
            style="filled,rounded"
            color="#e2e8f0"
            fillcolor="#fffbeb"
            penwidth=0.8
            color="#fde68a"

            wepp1 [label="Annual water balance\nand sediment model"     fillcolor="#fef3c7" color="#fbbf24"]
            wepp2 [label="Sediment discharge\n293 to 653 t/yr"          fillcolor="#fef3c7" color="#fbbf24"]
            wepp3 [label="Stream discharge\n2,124 to 2,125 mm/yr"       fillcolor="#fef3c7" color="#fbbf24"]

            wepp1 -> wepp2
            wepp2 -> wepp3 [style=dashed]
        }

        together [label="Complementary screening evidence\nWEPPcloud is benchmark, not validation"
                   shape=note fillcolor="#f8fafc" color="#94a3b8" fontsize=10]

        local3 -> together
        wepp3 -> together

        conclusion [label="Burned-footprint definition dominates\nuncertainty envelope"
                    shape=box fillcolor="#ffffff" color="#64748b" style="filled,rounded" fontsize=10.5]

        together -> conclusion
    }
    """
