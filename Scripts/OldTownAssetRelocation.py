"""Compare immutable historical actor snapshots across declared asset moves."""


def normalize_paths(value, relocations):
    if isinstance(value,str):
        for row in relocations:
            old,new=row['old'],row['new']
            # Exact package or object/class path; don't rewrite similarly named assets.
            if value==old or value.startswith(old+'.') or value.startswith(old+':'):
                value=new+value[len(old):]
        return value
    if isinstance(value,list):return [normalize_paths(v,relocations) for v in value]
    if isinstance(value,dict):return {k:normalize_paths(v,relocations) for k,v in value.items()}
    return value
