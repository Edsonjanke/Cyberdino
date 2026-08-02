# -*- coding: utf-8 -*-
"""Defaults metricos por operacao para a UI (base: sessionStore do EvoCAM,
com a furacao ja em RPM em vez de Vc). Cada default e um dict pronto para
SimpleNamespace(**d) -> params da estrategia."""

import copy


FACE = dict(
    operationType="FACE", title="Faceamento", material="Aco 1045",
    workOffset="G54", unitSystem="metric",
    roughingSFM=120, finishingSFM=145, maxSpindleRPM=1800,
    roughingFPR=0.25, finishingFPR=0.12, speedMode="SFM",
    spindleDir="CW", coolant="FLOOD", toolNumber=1, toolOffset=1,
    initialX=50.0, finalX=0.0, zStart=0.0, zEnd=0.1,
    roughingDOC=2.0, finishDOC=0.25, toolClearance=2.5, toolNoseRadius=0.8,
    finishOnly=False, useCannedCycle=False,
)

OD_TURN = dict(
    operationType="OD_TURN", title="Desbaste Ext", material="Aco 1045",
    workOffset="G54", unitSystem="metric",
    roughingSFM=120, finishingSFM=145, maxSpindleRPM=1800,
    roughingFPR=0.25, finishingFPR=0.12, speedMode="SFM",
    spindleDir="CW", coolant="FLOOD", toolNumber=1, toolOffset=1,
    initialX=50.0, finalX=38.0, zStart=2.5, zEnd=-38.0, filletRadius=0.0,
    roughingDOC=2.5, finishDOC=0.25, toolClearance=2.5, toolNoseRadius=0.8,
    useToolRadiusComp=False, useConstantSurface=True,
    finishOnly=False, useCannedCycle=False,
)

# Furacao: roughingSFM carrega o RPM (com cssMode=False o engine usa esse
# valor direto como rotacao). maxSpindleRPM limita.
DRILL = dict(
    operationType="DRILL", title="Furacao", material="Aco 1045",
    workOffset="G54", unitSystem="metric",
    roughingSFM=1000, finishingSFM=1000, maxSpindleRPM=2500,
    roughingFPR=0.12, finishingFPR=0.084, speedMode="RPM",
    spindleDir="CW", coolant="FLOOD", toolNumber=5, toolOffset=5,
    drillDiameter=10.0, zStart=2.0, zEnd=-25.0, peckDepth=2.0,
    dwellSeconds=0, toolClearance=2.5, drillPointAngle=118,
    useCannedCycle=False,
)

# Rosca externa. spindleRPM define a rotacao (G97). Na maquina back-tool,
# M4 = rosca direita (ver memoria feedback_thread_direction).
THREAD = dict(
    operationType="THREAD_EXTERNAL", title="Rosca", material="Aco 1045",
    workOffset="G54", unitSystem="metric",
    roughingSFM=0, finishingSFM=0, maxSpindleRPM=1800,
    roughingFPR=0, finishingFPR=0, speedMode="RPM",
    spindleDir="CW", coolant="FLOOD", toolNumber=1, toolOffset=1,
    side="EXTERNAL", xStart=25.0, xEnd=25.0, zStart=2.0, zEnd=-25.0,
    clearance=2.5, threadType="metric", pitch=1.0, tpi=0, threadAngle=60,
    minorDiameter=0.0, passes=0, springPasses=2, depthOfCut=0,
    spindleRPM=800, leadInLength=0, leadOutLength=0, infeedAngle=0,
    useCannedCycle=False,
)

ID_TURN = dict(
    operationType="ID_TURN", title="Desbaste Int", material="6061-T6 Aluminum",
    workOffset="G54", unitSystem="metric",
    roughingSFM=120, finishingSFM=145, maxSpindleRPM=1800,
    roughingFPR=0.15, finishingFPR=0.08, speedMode="SFM",
    spindleDir="CW", coolant="FLOOD", toolNumber=2, toolOffset=2,
    mode="BASIC",
    initialX=20.0, finalX=28.0, zStart=2.5, zEnd=-30.0,
    filletRadius=0.0, pilotEnd=0.0, faceRoughDOC=0.5,
    idRoughDOC=1.5, finishDOC=0.2, toolClearance=2.0, toolNoseRadius=0.4,
    useToolRadiusComp=False, finishOnly=False, useCannedCycle=False,
)



CHAMFER = dict(
    operationType="CHAMFER", title="Chanfro", material="6061-T6 Aluminum",
    workOffset="G54", unitSystem="metric",
    roughingSFM=120, finishingSFM=145, maxSpindleRPM=1800,
    roughingFPR=0.15, finishingFPR=0.08,
    speedMode="RPM", spindleDir="CW", coolant="FLOOD",
    toolNumber=3, toolOffset=3,
    mode="CHAMFER", side="OD",
    x=50.0, zStart=0.0, zEnd=-2.0,
    chamferAngle=45, chamferLength=2.0,
    roughingDOC=1.0, finishDOC=0.15, toolClearance=2.5,
)


GROOVE = dict(
    operationType="GROOVE", mode="GROOVE", title="Canal",
    material="6061-T6 Aluminum", workOffset="G54", unitSystem="metric",
    roughingSFM=80, finishingSFM=100, maxSpindleRPM=1800,
    roughingFPR=0.08, finishingFPR=0.04,
    speedMode="RPM", spindleDir="CW", coolant="FLOOD",
    toolNumber=4, toolOffset=4,
    initialX=50.0, finalX=40.0, zStart=0.0, zEnd=-5.0,
    grooveWidth=3.0, toolWidth=3.0,
    plungeFPR=0.05, roughingDOC=1.0, finishDOC=0.15, toolClearance=2.5,
    retract=1.0, peck=5.0, edgeBreak=0.3,
    useCannedCycle=False,
)



DEFAULTS = {
    "FACE": FACE,
    "OD_TURN": OD_TURN,
    "ID_TURN": ID_TURN,
    "CHAMFER": CHAMFER,
    "GROOVE": GROOVE,
    "DRILL": DRILL,
    "THREAD_EXTERNAL": THREAD,
}


def default_params(op_key):
    """Copia profunda do default para o op_key ('FACE','OD_TURN','DRILL',
    'THREAD_EXTERNAL')."""
    return copy.deepcopy(DEFAULTS[op_key])
