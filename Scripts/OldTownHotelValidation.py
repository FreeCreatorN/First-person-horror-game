"""Standing capsule checks on real supported hotel and street routes."""
from AuditOldTownRevision import _route_samples,_support,_step_probe

def route_probe(world,points):
    samples=[];failures=[];previous=None
    for planned in _route_samples(points):
        z=_support(world,planned,above=45,below=45)
        row={'planned_foot_cm':planned,'support_z_cm':z,'passed':False}
        if z is not None and abs(z-planned[2])<=10.05:
            probe=_step_probe(world,planned[:2]+[z],34,180)
            row.update(probe=probe,passed=probe['passed'] and (previous is None or abs(z-previous)<=10.05))
            previous=z
        samples.append(row)
        if not row['passed']:failures.append(row)
    return {'passed':len(points)>=2 and bool(samples) and not failures,'samples':samples,'sample_count':len(samples),'failures':failures,
            'capsule_radius_cm':34,'capsule_height_cm':180,'scope':'Standing headroom; lifted headroom is tested only when a real low riser requires a step.'}
