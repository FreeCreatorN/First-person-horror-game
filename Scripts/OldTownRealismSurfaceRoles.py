"""Route the former shared concrete material by measured surface use."""
def concrete_role(actor,component,record):
    label=(actor+' '+component).lower()
    # A horizontal sill or cornice belongs to the facade finish as well.
    if any(w in label for w in ('wall','column','post','pole','cornice','beam','lintel','windowreveal','canopy','roof','ceiling')):
        return 'ConcreteWall'
    if any(w in label for w in ('floor','slab','platform','landing','roadrevision','sidewalk','courtyard','ground')):
        return 'Concrete'
    bounds=record['world_render_bounds_before_wpo_cm']
    size=[hi-lo for lo,hi in zip(*bounds)]
    return 'Concrete' if size[2]<=min(size[:2])*.35 else 'ConcreteWall'
