"""Negative controls for coverage, hinge ancestry and future moving collision."""
import copy
import unittest
from types import SimpleNamespace

from Scripts.AuditOldTownOpeningComponents import validate_manifest, portal_id_for, _sample_lines
from Scripts.OldTownArchitectureSealPlan import window_plan


def component(name,parent=None,asset=None,movable=False,blocking=False,location=(0,0,0)):
    return {'name':name,'parent':parent,'asset':asset,'mobility':'MOVABLE' if movable else 'STATIC',
            'collision':'QUERY_AND_PHYSICS' if blocking else 'NO_COLLISION',
            'relative_location':list(location),'relative_rotation':[0,0,0],'relative_scale':[1,1,1]}


def building():
    b = SimpleNamespace(label='TestHouse', width=1000.,depth=900.,ground=11.,count=2,
                        floors=[11.,341.],high=[500.,900.,681.],normal_axis=1,u_axis=0,inward=1.,
                        door_width=140.,door_height=230.,portals=[{'wall':'Front','coordinate':0.,'primary':True}])
    b.world = lambda u,v,z:[u,v,z]
    b.world_box = lambda low,high:(list(low),list(high))
    return b


def door_row(b):
    frame,leaf = '/Game/Opening/SM_Frame','/Game/Opening/SM_DoorLeaf'
    return {'actor':'OpeningDoor_'+b.label,'building':b.label,'portal_id':portal_id_for(b,b.portals[0]),
            'kind':'building_entry','opening_width':140.,'opening_height':230.,'hinge_side':1,
            'frame_asset':frame,'leaf_asset':leaf,'world_center':[0.,0.,11.],
            'entry_foot':[0.,-50.,11.],'axes':{'across':[1,0,0],'inward':[0,1,0]},
            'closed_hinges':{'DoorHinge':[0,0,0]},'open_hinges':{'DoorHinge':[0,-90,0]},
            'components':[component('OpeningRoot'),component('FixedFrame','OpeningRoot',frame),
                          component('DoorHinge','OpeningRoot',movable=True),
                          component('DoorLeaf','DoorHinge',leaf,True),
                          component('LeafCollision','DoorHinge',movable=True,blocking=True,location=(0,66,112))]}


def window_row(b,w):
    frame,sash,glass = '/Game/Opening/SM_Frame','/Game/Opening/SM_Sash','/Game/Opening/SM_Glass'
    return {'actor':'OpeningWindow_'+w['name'],'window_id':w['name'],'building':b.label,
            'width':w['width'],'height':w['height'],'world_center':b.world(w['u'],w['v'],w['z']),
            'axes':{'across':[1,0,0],'inward':[0,1,0]},'frame_asset':frame,
            'closed_hinges':{'LeftHinge':[0,0,0],'RightHinge':[0,0,0]},
            'open_hinges':{'LeftHinge':[0,90,0],'RightHinge':[0,-90,0]},
            'components':[component('OpeningRoot'),component('FixedFrame','OpeningRoot',frame),
                          component('LeftHinge','OpeningRoot',movable=True),
                          component('RightHinge','OpeningRoot',movable=True),
                          component('LeftSash','LeftHinge',sash,True),component('RightSash','RightHinge',sash,True),
                          component('LeftGlass','LeftSash',glass,True,True),component('RightGlass','RightSash',glass,True,True)]}


class OpeningManifestTests(unittest.TestCase):
    def setUp(self):
        self.b = building()
        self.report = {'opening_components':{'schema_version':1,'doors':[door_row(self.b)],
                       'windows':[window_row(self.b,w) for w in window_plan(self.b)]}}

    def validate(self):
        return validate_manifest([self.b],self.report)

    def fails(self,part):
        result = self.validate()
        self.assertFalse(result['pass'])
        self.assertTrue(any(part in name for name in result['failures']),result['failures'])

    def test_valid_complete_coverage_and_moving_children(self):
        result = self.validate()
        self.assertTrue(result['pass'],result['failures'])
        self.assertEqual(result['statistics']['building_window_count'],4)

    def test_same_count_duplicate_window_cannot_hide_missing_opening(self):
        windows = self.report['opening_components']['windows']
        windows[-1] = copy.deepcopy(windows[0]);windows[-1]['actor'] = 'DifferentActor'
        self.fails('independent_window_coverage')

    def test_unknown_window_cannot_replace_expected_id(self):
        self.report['opening_components']['windows'][0]['window_id'] = 'GhostOpening'
        self.fails('independent_window_coverage')

    def test_portal_id_derived_from_real_wall_and_coordinate(self):
        self.report['opening_components']['doors'][0]['portal_id'] = 'TestHouse::Rear_0'
        self.fails('independent_entry_coverage')

    def test_frame_geometry_cannot_drift_while_id_is_correct(self):
        self.report['opening_components']['windows'][0]['world_center'][0] += 20.
        self.fails('independent_window_geometry')

    def test_static_glass_fails(self):
        row = self.report['opening_components']['windows'][0]
        next(c for c in row['components'] if c['name']=='LeftGlass')['mobility'] = 'STATIC'
        self.fails('moving_part:LeftGlass')

    def test_glass_attached_to_fixed_frame_fails(self):
        row = self.report['opening_components']['windows'][0]
        next(c for c in row['components'] if c['name']=='LeftGlass')['parent'] = 'FixedFrame'
        self.fails('moving_part:LeftGlass')

    def test_visual_glass_without_moving_collision_fails(self):
        row = self.report['opening_components']['windows'][0]
        next(c for c in row['components'] if c['name']=='LeftGlass')['collision'] = 'NO_COLLISION'
        self.fails('movable_hinge:LeftHinge')

    def test_old_fixed_door_collision_cannot_satisfy_hinge(self):
        row = self.report['opening_components']['doors'][0]
        next(c for c in row['components'] if c['name']=='LeafCollision')['parent'] = 'OpeningRoot'
        self.fails('movable_hinge:DoorHinge')

    def test_wrong_rotation_axis_fails(self):
        self.report['opening_components']['doors'][0]['open_hinges']['DoorHinge'] = [0,0,90]
        self.fails('movable_hinge:DoorHinge')

    def test_parent_cycle_fails_without_hanging(self):
        row = self.report['opening_components']['windows'][0]
        next(c for c in row['components'] if c['name']=='LeftHinge')['parent'] = 'LeftSash'
        self.fails('component_graph:LeftHinge')

    def test_unknown_parent_fails(self):
        row = self.report['opening_components']['doors'][0]
        next(c for c in row['components'] if c['name']=='DoorLeaf')['parent'] = 'MissingPivot'
        self.fails('component_graph:DoorLeaf')

    def test_guest_openings_need_independent_room_plan(self):
        door = copy.deepcopy(self.report['opening_components']['doors'][0])
        door.update(actor='GuestDoor',kind='hotel_guest',portal_id='Hotel::Room101')
        self.report['opening_components']['doors'].append(door)
        self.fails('independent_guest_door_coverage')

    def test_independently_planned_guest_windows_and_doors_pass(self):
        door = copy.deepcopy(self.report['opening_components']['doors'][0])
        door.update(actor='GuestDoor',kind='hotel_guest',portal_id='Hotel::Room101')
        window = copy.deepcopy(self.report['opening_components']['windows'][0])
        window.update(actor='GuestWindow',window_id='Hotel::Room101Window',kind='hotel_guest')
        self.report['opening_components']['doors'].append(door)
        self.report['opening_components']['windows'].append(window)
        self.report['hotel_plan'] = {
            'guest_rooms':[dict(door_id=door['portal_id'],building=self.b.label,world_center=door['world_center'],
                                opening_width=140.,opening_height=230.,axes=door['axes'])],
            'guest_windows':[dict(window_id=window['window_id'],building=self.b.label,world_center=window['world_center'],
                                  width=125.,height=120.,axes=window['axes'])]}
        result = self.validate()
        self.assertTrue(result['pass'],result['failures'])
        self.assertEqual(result['statistics']['hotel_guest_door_count'],1)
        self.assertEqual(result['statistics']['hotel_guest_window_count'],1)

    def test_guest_door_wrong_room_position_fails(self):
        self.test_independently_planned_guest_windows_and_doors_pass()
        self.report['opening_components']['doors'][-1]['world_center'] = [90.,0.,11.]
        self.fails('independent_hotel_geometry')

    def test_door_trace_is_at_half_height_above_floor(self):
        start,end = next(_sample_lines(self.report['opening_components']['doors'][0],True))
        self.assertEqual(start[2],126.)
        self.assertEqual(end[2],126.)

    def test_missing_scene_world_is_not_a_success(self):
        from Scripts.AuditOldTownOpeningComponents import run
        result = run(None,[],[self.b],self.report)
        self.assertFalse(result['pass'])
        self.assertIn('loaded_unreal_world_required',result['failures'])


if __name__ == '__main__':
    unittest.main()
