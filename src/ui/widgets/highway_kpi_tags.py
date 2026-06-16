from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from src.domain.test_functions import HIGHWAY_TEST_FUNCTION

HIGHWAY_MARKING_SCHEMA = "highway_kpi_test"
HIGHWAY_PROBLEM_TAB = "Highway KPI"

HIGHWAY_TEST_SCENES: Sequence[str] = (
    "主路直道",
    "主路弯道",
    "隧道",
    "收费站通行",
    "拥堵路段",
    "施工路段",
    "进出服务区",
    "匝道互通",
    "特殊车辆",
    "Bias",
    "切入切出",
    "避障绕行",
    "横向控制",
    "纵向控制",
    "人机共驾",
    "场景记录",
)

HIGHWAY_PROBLEM_DESCRIPTIONS: Sequence[str] = (
    "走错路",
    "不减速/制动不足",
    "制动过晚",
    "异常减速",
    "加减速顿挫",
    "限速不合理",
    "不加速/加速慢",
    "加速猛/异常加速",
    "制动力过大",
    "冲出车道",
    "方向盘大幅快速摆动",
    "摆动/蛇形",
    "贴边/压线",
    "反复偏移",
    "危险偏移",
    "未偏移避让/避让不够",
    "行车功能异常降级至L2",
    "行车功能异常降级至ACC",
    "行车功能异常退出",
    "SR语音播报/tips提示/画面显示异常",
    "危险变道/绕行",
    "实线变道",
    "变道不发起/发起晚",
    "导航变道时机不合理",
    "不合理/不必要变道",
    "变道动作扭捏/折回",
    "连续变道",
    "不打灯/乱打灯",
    "施工场景误作动",
    "下匝道成功",
    "下匝道失败",
    "高速互通通过成功",
    "高速互通通过失败",
    "分/合流成功",
    "高速收费站通行成功",
    "高速收费站通行体验差",
    "高速收费站通行失败",
    "施工场景正常作动",
    "施工场景作动失败/异常",
    "下服务区成功",
    "出服务区成功",
    "无|None",
)

HIGHWAY_EGO_ACTIONS: Sequence[str] = (
    "安全接管",
    "体验接管",
    "无|None",
)

HIGHWAY_SEVERITY_LEVELS: Sequence[str] = (
    "一般|C",
    "中等|B",
    "严重|A",
    "事故级|S",
    "无|None",
)


@dataclass(frozen=True)
class HighwayKpiTagCatalog:
    test_scenes: Sequence[str]
    problem_descriptions: Sequence[str]
    ego_actions: Sequence[str]
    severity_levels: Sequence[str]

    def problem_options(self) -> Dict[str, List[str]]:
        return {HIGHWAY_PROBLEM_TAB: list(self.problem_descriptions)}


def load_highway_kpi_tag_catalog() -> HighwayKpiTagCatalog:
    return HighwayKpiTagCatalog(
        test_scenes=HIGHWAY_TEST_SCENES,
        problem_descriptions=HIGHWAY_PROBLEM_DESCRIPTIONS,
        ego_actions=HIGHWAY_EGO_ACTIONS,
        severity_levels=HIGHWAY_SEVERITY_LEVELS,
    )
