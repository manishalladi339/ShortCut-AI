import { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ScrollView, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authApi } from '@/src/api/auth';
import { Input } from '@/src/components/ui/Input';
import { Button } from '@/src/components/ui/Button';
import { colors } from '@/src/theme';
export default function ResetPassword() {
  const {token}=useLocalSearchParams<{token:string}>(); const router=useRouter();
  const [password,setPassword]=useState(''); const [confirm,setConfirm]=useState('');
  const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [done,setDone]=useState(false);
  async function submit(){setError('');if(!token){setError('Reset link is missing. Request a new link.');return;}if(password!==confirm){setError('Passwords do not match.');return;}setBusy(true);try{await authApi.resetPassword(token,password);setDone(true);}catch(e:any){setError(e?.message||'Reset failed');}finally{setBusy(false);}}
  return <SafeAreaView style={{flex:1,backgroundColor:colors.bg}}><ScrollView contentContainerStyle={{padding:24,gap:20,maxWidth:500,width:'100%',alignSelf:'center'}}><Text style={{fontSize:28,color:colors.textHigh,fontWeight:'700'}}>Set a new password</Text>{error?<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>:null}{done?<><Text style={{color:colors.success}}>Password updated. Sign in with your new password.</Text><Button label="Sign in" onPress={()=>router.replace('/(auth)/sign-in')}/></>:<><Input label="New password" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none"/><Input label="Confirm password" value={confirm} onChangeText={setConfirm} secureTextEntry autoCapitalize="none"/><Button label="Reset password" loading={busy} onPress={submit}/></>}</ScrollView></SafeAreaView>;
}
