"""Central PlateLink application actions, shared by the HTTP dashboard and Orca client."""
from .core import Store,review
from .bridge import inventory

def dispatch(root,config,m,host=None):
    action=m.get('action');host=host or {'printer':'','bed_type':None,'bed_temp':[],'materials':[]}
    store=Store(root);msgs=[];spool=None
    if action=='refresh_live':return [{'type':'live',**inventory(config)}]
    if action=='add_plate':store.add_plate(int(m['revision']),m['plate'])
    elif action=='edit_plate':store.edit_plate(int(m['revision']),m['identifier'],m['plate'])
    elif action=='mount':store.mount(int(m['revision']),m['identifier'],m['face'],m['printer'])
    elif action=='unmount':store.unmount(int(m['revision']),m['printer'])
    elif action=='event':store.event(int(m['revision']),m['identifier'],m['face'],m['kind'],m['notes'],m.get('hours',0),m.get('spool_id'))
    elif action=='recipe':store.recipe(int(m['revision']),m['identifier'],m['face'],m['recipe'])
    elif action=='export':
        from pathlib import Path
        path=store.export();msgs.append({'type':'exported','path':'exports/'+Path(path).name})
    elif action=='label':
        from pathlib import Path
        label=store.label(m['identifier']);label['path']='exports/'+Path(label['path']).name;msgs.append({'type':'label',**label})
    elif action not in ('refresh','review'):raise ValueError('Acción no permitida')
    if m.get('spool_id'):
        live=inventory(config);spool=next((s for s in live['spools'] if s['id']==int(m['spool_id'])),None)
    state=store.read()
    msgs.append({'type':'state','state':state,'host':host,'config':config,'review':review(state,host,spool),'completed_action':action})
    return msgs
