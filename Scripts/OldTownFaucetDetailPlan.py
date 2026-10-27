"""Small old-hotel faucet additions, centimetres; existing basin stays intact."""
SCHEMA='OldTownFaucetDetailsV1'
SOURCE_ASSET='/Game/CodexGenerated/OldTown/Meshes/BasinConnections_20261011/SM_OTS_Arch_Washbasin_Connected'
def primitive_specs():
    return [dict(name=n,kind='cylinder',center=c,radius=r,height=h,axis=a,radial_sides=24,material_id=0) for n,c,r,h,a in (
        ('FaucetSleeve',[16.,0.,89.2],1.3,9.6,[0.,0.,1.]),
        ('FaucetSpout',[10.,0.,92.4],1.05,12.,[1.,0.,0.]),
        ('FaucetDownspout',[4.,0.,90.9],.95,3.2,[0.,0.,1.]),
        ('FaucetAerator',[4.,0.,89.55],1.1,.85,[0.,0.,1.]),
        ('FaucetValve',[16.,0.,94.1],.65,1.9,[0.,0.,1.]),
        ('FaucetCap',[16.,0.,95.3],1.85,1.5,[0.,0.,1.]),
        ('FaucetHandle',[16.,0.,95.3],.65,6.,[0.,1.,0.]))]
CONNECTION_WITNESSES=[
    dict(name='StubIntoSleeve',point=[16.,0.,84.7],parts=['tap','FaucetSleeve']),
    dict(name='SleeveIntoSpout',point=[15.5,0.,92.4],parts=['FaucetSleeve','FaucetSpout']),
    dict(name='SpoutIntoDrop',point=[4.5,0.,92.4],parts=['FaucetSpout','FaucetDownspout']),
    dict(name='DropIntoAerator',point=[4.,0.,89.7],parts=['FaucetDownspout','FaucetAerator']),
    dict(name='SleeveIntoValve',point=[16.,0.,93.6],parts=['FaucetSleeve','FaucetValve']),
    dict(name='ValveIntoCap',point=[16.,0.,94.8],parts=['FaucetValve','FaucetCap']),
    dict(name='CapIntoHandle',point=[16.,1.,95.3],parts=['FaucetCap','FaucetHandle'])]
LOCAL_ENVELOPE=[[-22.5,-30.,0.],[22.5,30.,96.05]]
