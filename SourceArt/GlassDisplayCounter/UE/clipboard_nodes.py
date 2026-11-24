"""Write the two display-counter door events in Unreal's clipboard format.

Paste into BP_GlassDisplayCounter's EventGraph, then compile. Each Custom
Event takes a Boolean Open input. Its one latent action can be retargeted
while in motion, and the other door uses a different latent action.
"""

from dataclasses import dataclass, field
from pathlib import Path
import uuid


def identifier():
    return uuid.uuid4().hex.upper()


def quoted(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


@dataclass
class Pin:
    name: str
    category: str
    out: bool = False
    subtype: str = ''
    type_object: str = ''
    default: str | None = None
    default_object: str = ''
    hidden: bool = False
    reference: bool = False
    uuid: str = field(default_factory=identifier)
    links: list = field(default_factory=list)

    def line(self):
        fields = [f'PinId={self.uuid}', f'PinName={quoted(self.name)}']
        if self.out:
            fields.append('Direction="EGPD_Output"')
        fields.append(f'PinType.PinCategory={quoted(self.category)}')
        if self.subtype:
            fields.append(f'PinType.PinSubCategory={quoted(self.subtype)}')
        if self.type_object:
            fields.append(f'PinType.PinSubCategoryObject={quoted(self.type_object)}')
        if self.reference:
            fields.append('PinType.bIsReference=True')
        if self.default is not None:
            fields.append(f'DefaultValue={quoted(self.default)}')
        if self.default_object:
            fields.append(f'DefaultObject={quoted(self.default_object)}')
        if self.links:
            endpoints = ''.join(f'{node} {pin_uuid},' for node, pin_uuid in self.links)
            fields.append(f'LinkedTo=({endpoints})')
        if self.hidden:
            fields.append('bHidden=True')
        return '   CustomProperties Pin (' + ','.join(fields) + ',)'


@dataclass
class Node:
    class_name: str
    name: str
    x: int
    y: int
    properties: list
    pins: list

    def by_name(self, name):
        return next(pin for pin in self.pins if pin.name == name)

    def lines(self):
        lines = [f'Begin Object Class=/Script/BlueprintGraph.{self.class_name} Name={quoted(self.name)}',
                 f'   NodePosX={self.x}', f'   NodePosY={self.y}', f'   NodeGuid={identifier()}']
        lines.extend('   ' + prop for prop in self.properties)
        lines.extend(pin.line() for pin in self.pins)
        lines.append('End Object')
        return lines


def link(source, output, target, input_pin):
    left = source.by_name(output)
    right = target.by_name(input_pin)
    assert left.out and not right.out
    left.links.append((target.name, right.uuid))
    right.links.append((source.name, left.uuid))


def class_ref(name):
    return f"/Script/CoreUObject.Class'/Script/Engine.{name}'"


def struct_ref(module, name):
    return f"/Script/CoreUObject.ScriptStruct'/Script/{module}.{name}'"


def function_ref(owner, function):
    return f'FunctionReference=(MemberParent={quoted(class_ref(owner))},MemberName={quoted(function)})'


def function_self(owner):
    return Pin('self', 'object', type_object=class_ref(owner), hidden=True,
               default_object=f'/Script/Engine.Default__{owner}')


VECTOR = struct_ref('CoreUObject', 'Vector')
ROTATOR = struct_ref('CoreUObject', 'Rotator')


def vector_text(location):
    return ','.join(f'{value:.8f}' for value in location)


def make_side(side, component, event_name, start, stop, duration):
    index = 100 if side == 'left' else 200
    y = 0 if side == 'left' else 480
    event = Node('K2Node_CustomEvent', f'K2Node_CustomEvent_{index}', 0, y,
                 [f'CustomFunctionName={quoted(event_name)}', 'bIsEditable=True',
                  'CustomProperties UserDefinedPin (PinName="Open",PinType=(PinCategory="bool"),DesiredPinDirection=EGPD_Output)'],
                 [Pin('OutputDelegate', 'delegate', out=True), Pin('then', 'exec', out=True), Pin('Open', 'bool', out=True)])
    getter = Node('K2Node_VariableGet', f'K2Node_VariableGet_{index}', 16, y+188,
                  [f'VariableReference=(MemberName={quoted(component)},bSelfContext=True)'],
                  [Pin(component, 'object', out=True, type_object=class_ref('StaticMeshComponent')),
                   Pin('self', 'object', subtype='self', hidden=True)])
    select = Node('K2Node_CallFunction', f'K2Node_CallFunction_{index}', 288, y+180,
                  [function_ref('KismetMathLibrary', 'SelectVector'), 'bIsPureFunc=True'],
                  [function_self('KismetMathLibrary'),
                   Pin('A', 'struct', type_object=VECTOR, default=vector_text(stop)),
                   Pin('B', 'struct', type_object=VECTOR, default=vector_text(start)),
                   Pin('bPickA', 'bool', default='false'),
                   Pin('ReturnValue', 'struct', out=True, type_object=VECTOR)])
    move = Node('K2Node_CallFunction', f'K2Node_CallFunction_{index+1}', 650, y,
                [function_ref('KismetSystemLibrary', 'MoveComponentTo')],
                [Pin('Move', 'exec'), Pin('Stop', 'exec'), Pin('Return', 'exec'), Pin('then', 'exec', out=True),
                 function_self('KismetSystemLibrary'),
                 Pin('Component', 'object', type_object=class_ref('SceneComponent')),
                 Pin('TargetRelativeLocation', 'struct', type_object=VECTOR),
                 Pin('TargetRelativeRotation', 'struct', type_object=ROTATOR, default='0,0,0'),
                 Pin('bEaseOut', 'bool', default='true'), Pin('bEaseIn', 'bool', default='true'),
                 Pin('OverTime', 'real', subtype='float', default=f'{duration:.6f}'),
                 Pin('bForceShortestRotationPath', 'bool', default='true'),
                 Pin('MoveAction', 'byte', type_object="/Script/CoreUObject.Enum'/Script/Engine.EMoveComponentAction'",
                     default='Move', hidden=True),
                 Pin('LatentInfo', 'struct', type_object=struct_ref('Engine', 'LatentActionInfo'), hidden=True)])
    link(event, 'then', move, 'Move')
    link(event, 'Open', select, 'bPickA')
    link(getter, component, move, 'Component')
    link(select, 'ReturnValue', move, 'TargetRelativeLocation')
    return event, getter, select, move


def write_sliding_nodes(directory, travel, components, events, duration):
    nodes = []
    for side in ('left', 'right'):
        points = travel[side]
        nodes.extend(make_side(side, components[side], events[side], points['closed_ue_cm'], points['open_ue_cm'], duration))
    data = '\n'.join(line for node in nodes for line in node.lines()) + '\n'
    path = Path(directory) / 'SlidingDoorBlueprintNodes.txt'
    path.write_text(data, encoding='utf-8')
    return path
