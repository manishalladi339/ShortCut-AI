import { Alert as NativeAlert, Platform } from 'react-native';
type Action = {text?:string;style?:'default'|'cancel'|'destructive';onPress?:()=>void};
/** React Native Alert has no web implementation; keep feedback and confirmations visible. */
export const Alert = {
  alert(title:string,message?:string,actions?:Action[]){
    if(Platform.OS!=='web'){NativeAlert.alert(title,message,actions);return;}
    if(typeof window==='undefined')return;
    const text=[title,message].filter(Boolean).join('\n\n');
    if(actions&&actions.length>1){
      if(window.confirm(text)) actions.find(a=>a.style!=='cancel')?.onPress?.();
      else actions.find(a=>a.style==='cancel')?.onPress?.();
    }else{window.alert(text);actions?.[0]?.onPress?.();}
  },
};
