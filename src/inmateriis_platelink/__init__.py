"""PlateLink by Inmateriis: popup client for the shared laboratory inventory."""
import json
from pathlib import Path
import threading
import urllib.request
import urllib.error
from .core import VERSION,data_root
from .apply import apply_installed_bed,sync_installed_bed
from .bridge import option_values,scalar,base_url,NoRedirect,write_json
try:
    import orca
except ImportError:
    orca=None
PAGE=(Path(__file__).parent/'panel.html').read_text(encoding='utf-8').replace('{{VERSION}}',VERSION)
def host_snapshot():
    b=orca.host.preset_bundle();bed=scalar(option_values(b.full_config_value('curr_bed_type')))
    keys={'Cool Plate':'cool_plate_temp','Engineering Plate':'eng_plate_temp','High Temp Plate':'hot_plate_temp',
          'Textured PEI Plate':'textured_plate_temp','Textured Cool Plate':'textured_cool_plate_temp','Supertack Plate':'supertack_plate_temp'}
    return {'printer':b.current_printer_preset().name,'bed_type':bed,
            'can_select_bed':False,
            'bed_temp':option_values(b.full_config_value(keys.get(bed,'hot_plate_temp'))),
            'materials':option_values(b.full_config_value('filament_type'))}

def remote(url,message,host):
    req=urllib.request.Request(base_url(url)+'/api/action',data=json.dumps({**message,'_orca_host':host}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as r:
            raw=r.read(24*1024*1024+1)
    except urllib.error.HTTPError as e:
        try:raise ValueError(json.loads(e.read(10000)).get('error','Error del servidor PlateLink'))
        except (json.JSONDecodeError,AttributeError):raise ValueError('No se pudo completar la operación en PlateLink')
    if len(raw)>24*1024*1024:raise ValueError('Inventario demasiado grande')
    return json.loads(raw)['messages']
if orca is not None:
    class PlateWindow(orca.script.ScriptPluginCapabilityBase):
        def get_name(self):return 'PlateLink · Inventario compartido'
        def on_load(self):self.window=None;self.generation=0;self.busy=False
        def on_unload(self):self.generation+=1;self.window=None
        def execute(self):
            if self.window and self.window.is_open():self.window.close()
            self.generation+=1;self.busy=False
            self.window=orca.host.ui.create_window(html=PAGE,title='PlateLink by Inmateriis',width=1120,height=850,on_message=self.on_message)
            return orca.ExecutionResult.success('PlateLink abierto. Inventario compartido; sin control de impresoras.')
        def on_message(self,m):
            if not isinstance(m,dict) or self.busy:return
            win=self.window;root=data_root();path=root/'server.json'
            try:
                settings=json.loads(path.read_text()) if path.exists() else {'server_url':''}
                if m.get('action')=='save_config':
                    settings={'server_url':base_url(m['config']['platelink_url'])};write_json(path,settings);m={'action':'refresh'}
                if not settings.get('server_url'):
                    win.post({'type':'setup','message':'Configura la URL del servidor PlateLink en Conexiones.'});return
                host=host_snapshot();generation=self.generation;self.busy=True;win.post({'type':'busy'})
                def work():
                    try:
                        if m.get('action')=='apply_bed':
                            fresh=next(x for x in remote(settings['server_url'],{'action':'refresh'},host) if x.get('type')=='state')
                            bed=apply_installed_bed(m.get('installed'),fresh,host,orca.host)
                            host['bed_type']=bed
                            host['bed_temp']=[]
                            messages=remote(settings['server_url'],{'action':'refresh'},host)
                            for item in messages:
                                if item.get('type')=='state':item['bed_applied']=bed
                        else:
                            messages=remote(settings['server_url'],m,host)
                            if m.get('action')=='refresh':
                                fresh=next((x for x in messages if x.get('type')=='state'),None)
                                bed=sync_installed_bed(fresh or {},host,orca.host)
                                if bed:
                                    host['bed_type']=bed
                                    # These temperatures belonged to the previous category.
                                    # A subsequent UI snapshot supplies the new effective values.
                                    host['bed_temp']=[]
                                    messages=remote(settings['server_url'],{'action':'refresh'},host)
                                    for item in messages:
                                        if item.get('type')=='state':item['bed_applied']=bed
                        for msg in messages:
                            if msg.get('config') is not None:msg['config']['platelink_url']=settings['server_url']
                            if msg.get('path','').startswith('exports/'):msg['path']=settings['server_url'].rstrip('/')+'/'+msg['path']
                            if generation==self.generation and win.is_open():win.post(msg)
                    except Exception as e:
                        if generation==self.generation and win.is_open():win.post({'type':'error','message':str(e)})
                    finally:
                        if generation==self.generation:self.busy=False
                threading.Thread(target=work,daemon=True,name='PlateLink-central').start()
            except Exception as e:win.post({'type':'error','message':str(e)})
    @orca.plugin
    class PlateLinkInmateriis(orca.base):
        def register_capabilities(self):
            from .texture_window import TextureWindow
            orca.register_capability(TextureWindow)
            orca.register_capability(PlateWindow)
