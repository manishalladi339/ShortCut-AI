import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { projectsApi } from '@/src/api/projects';
import { editorApi, Export } from '@/src/api/editor';
import { Button } from '@/src/components/ui/Button';
import { colors } from '@/src/theme';
export default function Hub(){
 const router=useRouter();const [items,setItems]=useState<(Export&{projectTitle:string;projectId:string})[]>([]);const [error,setError]=useState('');const [loading,setLoading]=useState(true);
 const load=useCallback(async()=>{setLoading(true);setError('');try{const p=await projectsApi.list();const result=await Promise.all(p.items.map(async x=>(await editorApi.exports(x.id)).map(e=>({...e,projectTitle:x.title,projectId:x.id}))));setItems(result.flat().sort((a,b)=>b.created_at.localeCompare(a.created_at)));}catch(e:any){setError(e?.message||'Could not load exports');}finally{setLoading(false);}},[]);
 useFocusEffect(useCallback(()=>{load();},[load]));
 return <SafeAreaView style={{flex:1,backgroundColor:colors.bg}}><ScrollView contentContainerStyle={{padding:24,gap:20,paddingBottom:120}}><Text style={{fontSize:28,fontWeight:'700',color:colors.textHigh}}>Content Hub</Text><Text style={{color:colors.textMedium}}>Rendered videos from your projects. Open the editor to preview or download an export.</Text>{error?<Text style={{color:colors.danger}}>{error}</Text>:null}{loading?<ActivityIndicator color={colors.aiAccent}/>:null}{!loading&&!items.length?<Text style={{color:colors.textMedium}}>No exports yet. Create a project and render your first video.</Text>:null}{items.map(e=><View key={e.id} style={{padding:20,gap:12,backgroundColor:colors.surface1,borderRadius:16}}><Text style={{fontSize:18,color:colors.textHigh}}>{e.projectTitle}</Text><Text style={{color:colors.textMedium}}>Version {e.project_state_version} · {e.status}</Text><Button label="Open project" variant="secondary" onPress={()=>router.push(`/projects/${e.projectId}/editor` as any)}/></View>)}<Button label="Refresh exports" variant="ghost" onPress={load}/></ScrollView></SafeAreaView>;
}
