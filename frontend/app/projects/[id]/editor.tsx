import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useVideoPlayer, VideoView } from 'expo-video';
import { Asset, assetsApi } from '@/src/api/assets';
import { Clip, Job, EditPlan, editorApi, Export, ProjectState, Track, Version } from '@/src/api/editor';
import { Button } from '@/src/components/ui/Button';
import { colors, radius } from '@/src/theme';

function Player({url}:{url:string}) {
  const player = useVideoPlayer(url);
  return <VideoView player={player} style={{width:'100%', height:320, backgroundColor:'#000'}} nativeControls contentFit="contain" />;
}
const errorMessage = (e: unknown) => (e as {message?:string})?.message || 'Something went wrong. Please try again.';

export default function Editor() {
  const {id} = useLocalSearchParams<{id:string}>();
  const router = useRouter();
  const [state,setState] = useState<ProjectState|null>(null);
  const [assets,setAssets] = useState<Asset[]>([]);
  const [exports,setExports] = useState<Export[]>([]);
  const [versions,setVersions] = useState<Version[]>([]);
  const [plan,setPlan] = useState<EditPlan|null>(null);
  const [selected,setSelected] = useState<string[]>([]);
  const [objective,setObjective] = useState('Create a compelling short video with a clear opening and a strong ending.');
  const [duration,setDuration] = useState('45');
  const [music,setMusic] = useState<string|null>(null);
  const [captions,setCaptions] = useState(true);
  const [replace,setReplace] = useState(false);
  const [pipeline,setPipeline] = useState<Job|null>(null);
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [preview,setPreview] = useState<string|null>(null);
  const [editing,setEditing] = useState<{clip:Clip;track:Track}|null>(null);
  const [sourceStart,setSourceStart] = useState('0');
  const [clipDuration,setClipDuration] = useState('5');
  const [position,setPosition] = useState('0');
  const [volume,setVolume] = useState('1');
  const [captionText,setCaptionText] = useState('');
  const [captionStart,setCaptionStart] = useState('0');
  const [captionDuration,setCaptionDuration] = useState('3');
  const alive = useRef(true);
  const operating = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const sequence = state?.sequences.find(s=>s.id===state.active_sequence_id);
  const tps = sequence ? sequence.timebase.numerator / sequence.timebase.denominator : 1000;

  const load = useCallback(async () => {
    if (!id) return;
    const [s,a,e,v,p] = await Promise.all([editorApi.state(id),assetsApi.list({project_id:id}),editorApi.exports(id),editorApi.versions(id),editorApi.plans(id)]);
    if (!alive.current) return;
    setState(s);setAssets(a.items);setExports(e);setVersions(v);
    const proposal = p.find(x=>x.status==='proposed');
    setPlan(proposal ?? null);setSelected(proposal?.operations.map(o=>o.id) ?? []);
  },[id]);
  useFocusEffect(useCallback(()=>{load().catch(e=>setError(errorMessage(e)));},[load]));
  useEffect(()=>{
    const timer=setInterval(async()=>{
      if(operating.current) return;
      try {
        const [a,e,p] = await Promise.all([assetsApi.list({project_id:id}),editorApi.exports(id),editorApi.pipeline(id)]);
        if(alive.current){setAssets(a.items);setExports(e);setPipeline(p);}
      }catch { /* Preserve current view; explicit refresh surfaces connection errors. */ }
    },5000);
    return ()=>clearInterval(timer);
  },[id]);

  async function run(label:string, task:()=>Promise<void>) {
    if(operating.current) return;
    operating.current=true;setBusy(label);setError('');setNotice('');
    try { await task(); } catch(e) { if(alive.current)setError(errorMessage(e)); }
    finally { operating.current=false;if(alive.current)setBusy(''); }
  }
  async function waitJob(jobId:string,label:string) {
    const deadline = Date.now()+30*60*1000;
    while(alive.current && Date.now()<deadline) {
      const j=await editorApi.job(jobId);
      setBusy(`${label} · ${j.progress}%`);
      if(j.status==='succeeded') return;
      if(j.status==='failed'||j.status==='canceled') throw new Error(j.error_message || `${label} failed`);
      await new Promise(resolve=>setTimeout(resolve,2000));
    }
    throw new Error('Processing continues on the server. Reopen the project to check its status.');
  }
  async function analyze() {
    const list=await assetsApi.list({project_id:id});
    const videos=list.items.filter(a=>a.kind==='video'&&a.upload_status==='uploaded');
    if(!videos.length) throw new Error('Upload at least one video first.');
    for(const asset of videos) {
      if(asset.processing_status!=='ready') {
        if(!asset.processing_job_id) throw new Error(`${asset.filename} is not ready. Check its upload.`);
        await waitJob(asset.processing_job_id,`Preparing ${asset.filename}`);
      }
      const existing=await editorApi.intelligence(asset.id).catch((e)=>{
        if(e.code==='intelligence.not_found')return null;
        throw e;
      });
      if(existing?.status==='completed') continue;
      const job=await editorApi.analyze(asset.id);
      await waitJob(job.job_id,`Analyzing ${asset.filename}`);
    }
    setNotice('Media analysis is ready.');
  }
  function planBody() {
    const seconds=Number(duration);
    if(!Number.isFinite(seconds)||seconds<5||seconds>300) throw new Error('Choose a target between 5 and 300 seconds.');
    return {objective,target_duration_sec:seconds,include_captions:captions,music_asset_id:music};
  }
  async function makePlan() {
    const p=await editorApi.plan(id,planBody());setPlan(p);setSelected(p.operations.map(o=>o.id));
  }
  async function automatic() {
    const job=await editorApi.startPipeline(id,planBody());
    setPipeline(job);setNotice('Automatic editing started. You can leave this screen and return to check your export.');
  }
  async function edit(operation:string,payload:Record<string,unknown>) {
    if(!state||!sequence)return;
    const s=await editorApi.edit(id,state.version,operation,{sequence_id:sequence.id,...payload});
    setState(s);setVersions(await editorApi.versions(id));
  }
  async function addAsset(a:Asset) {
    if(!sequence)return;
    const track=sequence.tracks.find(t=>t.kind===(a.kind==='audio'?'audio':'video'));
    if(!track)throw new Error('The required track is missing. Restore a previous version.');
    const end=Math.max(0,...track.clips.map(c=>c.timeline_start+c.duration));
    const length=Math.max(1,Math.round(Math.min(a.duration_sec || 5,300)*tps));
    await edit('add_clip',{track_id:track.id,asset_id:a.id,timeline_start:end,duration:length,source_duration:length});
  }
  function chooseClip(clip:Clip,track:Track) {
    setEditing({clip,track});setSourceStart(String(clip.source_start/tps));setClipDuration(String(clip.duration/tps));setPosition(String(clip.timeline_start/tps));setVolume(String(clip.volume));
  }
  async function saveClip() {
    if(!editing||!state||!sequence)return;
    const nums=[Number(sourceStart),Number(clipDuration),Number(position),Number(volume)];
    if(nums.some(n=>!Number.isFinite(n))||nums[0]<0||nums[1]<=0||nums[2]<0||nums[3]<0||nums[3]>4)throw new Error('Enter valid source, duration, position, and volume values.');
    const next=JSON.parse(JSON.stringify(state)) as ProjectState;
    const clip=next.sequences.find(s=>s.id===sequence.id)!.tracks.find(t=>t.id===editing.track.id)!.clips.find(c=>c.id===editing.clip.id)!;
    Object.assign(clip,{source_start:Math.round(nums[0]*tps),duration:Math.round(nums[1]*tps),source_duration:Math.round(nums[1]*tps*clip.playback_rate),timeline_start:Math.round(nums[2]*tps),volume:nums[3]});
    setState(await editorApi.replace(id,next));setEditing(null);setVersions(await editorApi.versions(id));
  }
  const disabled=!!busy;
  return <SafeAreaView style={styles.root} edges={['top','bottom']}>
    <View style={styles.header}><Button label="Back" variant="ghost" onPress={()=>router.back()}/><Text style={styles.title}>Editing studio</Text><Button label="Refresh" variant="ghost" disabled={disabled} onPress={()=>run('Refreshing',load)}/></View>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      {error?<View style={styles.error}><Text accessibilityRole="alert" style={styles.text}>{error}</Text><Text style={styles.muted}>For a version conflict, refresh before editing again.</Text></View>:null}
      {busy?<View style={styles.row}><ActivityIndicator color={colors.aiAccent}/><Text accessibilityLiveRegion="polite" style={styles.text}>{busy}</Text></View>:null}
      {notice?<Text style={styles.success}>{notice}</Text>:null}
      {pipeline?<View style={styles.card}><Text style={styles.text}>Automatic edit · {pipeline.status} · {pipeline.progress}%</Text>{pipeline.error_message?<Text style={styles.muted}>{pipeline.error_message}</Text>:null}{pipeline.status==='succeeded'?<Button label="Load completed edit" onPress={()=>run('Loading edit',load)}/>:null}</View>:null}
      {!state?<Text style={styles.muted}>Loading project…</Text>:null}
      {preview?<View style={styles.card}><Player key={preview} url={preview}/><Button label="Close preview" variant="ghost" onPress={()=>setPreview(null)}/></View>:null}
      <View style={styles.card}>
        <Text style={styles.heading}>1. Source media</Text><Text style={styles.muted}>Upload clips, preview them, and add them to your timeline. AI analysis uses the videos in this project.</Text>
        <Button label="Upload media" disabled={disabled} onPress={()=>router.push({pathname:'/library',params:{project_id:id}})}/>
        {assets.map(a=><View key={a.id} style={styles.item}><Text style={styles.text}>{a.filename}</Text><Text style={styles.muted}>{a.kind} · {a.processing_status} · {a.duration_sec?.toFixed(1) ?? '—'} sec</Text>
          <View style={styles.row}><Button label="Add to timeline" variant="secondary" disabled={disabled||a.processing_status!=='ready'} onPress={()=>run('Adding clip',()=>addAsset(a))}/>
          {a.kind==='video'&&a.download_url?<Button label="Preview" variant="ghost" onPress={()=>setPreview(a.download_url)}/>:null}
          {a.kind==='audio'?<Button label={music===a.id?'Music selected':'Use as music'} variant={music===a.id?'ai':'ghost'} disabled={disabled||a.processing_status!=='ready'} onPress={()=>setMusic(music===a.id?null:a.id)}/>:null}</View></View>)}
      </View>
      <View style={styles.card}>
        <Text style={styles.heading}>2. Create with AI</Text>
        <Field label="What should this video communicate?" value={objective} onChange={setObjective} multiline/>
        <Field label="Target length (seconds)" value={duration} onChange={setDuration}/>
        <View style={styles.row}><Switch value={captions} onValueChange={setCaptions}/><Text style={styles.text}>Include captions</Text></View>
        <Button label="Create For Me · analyze, edit & export" variant="ai" disabled={disabled||!state} onPress={()=>run('Starting',automatic)}/>
        <Text style={styles.muted}>For an empty timeline. Uses your uploaded media and saves a version you can refine. Processing continues if you leave this screen.</Text>
        <View style={styles.row}><Button label="Analyze media" variant="secondary" disabled={disabled} onPress={()=>run('Analyzing media',analyze)}/><Button label="Propose an edit" variant="secondary" disabled={disabled||!state} onPress={()=>run('Planning edit',makePlan)}/></View>
        {plan?<View style={styles.item}><Text style={styles.heading}>Review proposed changes</Text><Text style={styles.text}>{plan.narrative_summary}</Text>
          {plan.operations.map(o=><Pressable key={o.id} disabled={disabled} accessibilityRole="checkbox" accessibilityState={{checked:selected.includes(o.id)}} onPress={()=>setSelected(s=>s.includes(o.id)?s.filter(x=>x!==o.id):[...s,o.id])} style={styles.item}><Text style={styles.text}>{selected.includes(o.id)?'☑':'☐'} {o.operation.replaceAll('_',' ')}</Text><Text style={styles.muted}>{o.reason}</Text></Pressable>)}
          <View style={styles.row}><Switch value={replace} onValueChange={setReplace}/><Text style={styles.text}>Replace existing video clips</Text></View>
          <Button label={`Apply ${selected.length} changes`} disabled={disabled||!selected.length} onPress={()=>run('Applying plan',async()=>{if(!state)return;setState(await editorApi.apply(id,plan.id,state.version,selected,replace));setPlan(null);setVersions(await editorApi.versions(id));})}/>
          {plan.caption_suggestion?<Text style={styles.muted}>Suggested post: {plan.caption_suggestion}</Text>:null}
        </View>:null}
      </View>
      <View style={styles.card}>
        <Text style={styles.heading}>3. Timeline · version {state?.version ?? '—'}</Text><Text style={styles.muted}>Changes save immediately. Select a clip to adjust its source range, timeline position, or volume.</Text>
        {sequence?.tracks.filter(t=>t.kind!=='caption').map(track=><View key={track.id} style={styles.item}><View style={styles.row}><Text style={styles.text}>{track.name}{track.muted?' · muted':''}</Text><Button label={track.muted?'Unmute':'Mute'} variant="ghost" disabled={disabled} onPress={()=>run('Updating track',()=>edit('set_track_properties',{track_id:track.id,muted:!track.muted}))}/></View>
          {track.clips.length===0?<Text style={styles.muted}>No clips</Text>:null}
          {track.clips.slice().sort((a,b)=>a.timeline_start-b.timeline_start).map(clip=><Pressable key={clip.id} disabled={disabled} onPress={()=>chooseClip(clip,track)} style={styles.clip}><Text style={styles.text}>{assets.find(a=>a.id===clip.asset_id)?.filename ?? 'Media clip'}</Text><Text style={styles.muted}>{(clip.timeline_start/tps).toFixed(1)}s → {((clip.timeline_start+clip.duration)/tps).toFixed(1)}s · source {(clip.source_start/tps).toFixed(1)}s</Text></Pressable>)}
        </View>)}
        {editing?<View style={styles.item}><Text style={styles.heading}>Edit selected clip</Text><Field label="Source start (seconds)" value={sourceStart} onChange={setSourceStart}/><Field label="Clip length (seconds)" value={clipDuration} onChange={setClipDuration}/><Field label="Timeline start (seconds)" value={position} onChange={setPosition}/><Field label="Volume (0–4)" value={volume} onChange={setVolume}/>
          <Button label="Save clip" disabled={disabled} onPress={()=>run('Saving clip',saveClip)}/>
          <View style={styles.row}><Button label="Split in half" variant="secondary" disabled={disabled} onPress={()=>run('Splitting clip',async()=>{await edit('split_clip',{track_id:editing.track.id,clip_id:editing.clip.id,split_at:editing.clip.timeline_start+Math.floor(editing.clip.duration/2)});setEditing(null);})}/><Button label="Remove clip" variant="danger" disabled={disabled} onPress={()=>run('Removing clip',async()=>{await edit('remove_clip',{track_id:editing.track.id,clip_id:editing.clip.id});setEditing(null);})}/><Button label="Cancel" variant="ghost" onPress={()=>setEditing(null)}/></View>
        </View>:null}
        <Text style={styles.heading}>Captions</Text>
        {sequence?.captions.map(c=><View key={c.id} style={styles.item}><Text style={styles.text}>{c.text}</Text><Text style={styles.muted}>{(c.start/tps).toFixed(1)}s · {(c.duration/tps).toFixed(1)}s</Text><Button label="Remove caption" variant="ghost" disabled={disabled} onPress={()=>run('Removing caption',()=>edit('remove_caption',{caption_id:c.id}))}/></View>)}
        <Field label="New caption" value={captionText} onChange={setCaptionText}/><Field label="Start (seconds)" value={captionStart} onChange={setCaptionStart}/><Field label="Duration (seconds)" value={captionDuration} onChange={setCaptionDuration}/>
        <Button label="Add caption" variant="secondary" disabled={disabled||!captionText.trim()} onPress={()=>run('Adding caption',async()=>{await edit('add_caption',{text:captionText.trim(),start:Math.round(Number(captionStart)*tps),duration:Math.round(Number(captionDuration)*tps)});setCaptionText('');})}/>
      </View>
      <View style={styles.card}><Text style={styles.heading}>4. Exports</Text><Button label="Render current timeline" variant="ai" disabled={disabled||!sequence?.tracks.some(t=>['video','overlay'].includes(t.kind)&&t.clips.length>0)} onPress={()=>run('Starting export',async()=>{await editorApi.export(id);setExports(await editorApi.exports(id));setNotice('Export queued. You can leave this screen and return when it is ready.');})}/>
        {exports.map(e=><View key={e.id} style={styles.item}><Text style={styles.text}>Version {e.project_state_version} · {e.status}</Text><Text style={styles.muted}>{new Date(e.created_at).toLocaleString()}</Text>{e.status==='failed'?<Button label="Show error" variant="ghost" onPress={()=>run('Checking export',async()=>{const job=await editorApi.job(e.job_id);throw new Error(job.error_message||'Export failed. Check the timeline and try again.');})}/>:null}{e.download_url?<View style={styles.row}><Button label="Watch export" variant="secondary" onPress={()=>setPreview(e.download_url)}/><Button label="Open / download MP4" variant="ghost" onPress={()=>run('Opening export',async()=>{const fresh=(await editorApi.exports(id)).find(x=>x.id===e.id);if(fresh?.download_url)await Linking.openURL(fresh.download_url);})}/></View>:null}</View>)}
      </View>
      <View style={styles.card}><Text style={styles.heading}>Version history</Text><Text style={styles.muted}>Restore creates a new version and keeps the previous history.</Text>{versions.slice(0,12).map(v=><View key={v.version} style={styles.row}><Text style={styles.text}>v{v.version} · {v.operation}</Text><Button label="Restore" variant="ghost" disabled={disabled||v.version===state?.version} onPress={()=>run('Restoring version',async()=>{if(!state)return;setState(await editorApi.restore(id,v.version,state.version));setVersions(await editorApi.versions(id));setEditing(null);})}/></View>)}</View>
    </ScrollView>
  </SafeAreaView>;
}
function Field({label,value,onChange,multiline=false}:{label:string;value:string;onChange:(v:string)=>void;multiline?:boolean}) {
  return <View style={{gap:6}}><Text style={styles.muted}>{label}</Text><TextInput accessibilityLabel={label} style={[styles.input,multiline&&{minHeight:90}]} value={value} onChangeText={onChange} multiline={multiline} placeholderTextColor={colors.textLow}/></View>;
}
const styles=StyleSheet.create({
  root:{flex:1,backgroundColor:colors.bg},header:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',borderBottomWidth:1,borderColor:colors.border},
  title:{color:colors.textHigh,fontSize:18,fontWeight:'700',flexShrink:1},content:{padding:20,gap:20,maxWidth:1050,width:'100%',alignSelf:'center',paddingBottom:60},
  card:{padding:20,gap:16,backgroundColor:colors.surface1,borderRadius:radius.lg,borderWidth:1,borderColor:colors.border},
  heading:{fontSize:20,fontWeight:'700',color:colors.textHigh},text:{fontSize:15,color:colors.textHigh,lineHeight:23,flexShrink:1},muted:{fontSize:13,color:colors.textMedium,lineHeight:20},
  row:{flexDirection:'row',alignItems:'center',flexWrap:'wrap',gap:10},item:{gap:10,paddingVertical:12,borderTopWidth:1,borderColor:colors.border},
  clip:{padding:14,borderRadius:10,backgroundColor:colors.surface2,borderLeftWidth:3,borderLeftColor:colors.aiAccent},input:{borderWidth:1,borderColor:colors.border,borderRadius:10,padding:12,color:colors.textHigh,backgroundColor:colors.bg,fontSize:15},
  error:{padding:16,gap:8,borderWidth:1,borderColor:colors.danger,borderRadius:10},success:{color:colors.success,fontSize:15},
});
