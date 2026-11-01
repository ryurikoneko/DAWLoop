// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
export function windowsNotifier(Notification,icon,platform=process.platform) {
  const active=new Set();
  return ({title,body,onClick,onClose,id,groupId})=>{
    if(platform!=='win32'||!Notification.isSupported())return false;
    const toast=new Notification({title,body,icon,id,groupId,silent:true,timeoutType:'default'});
    active.add(toast);
    toast.once('click',()=>{Promise.resolve().then(onClick).catch(()=>{});});
    toast.once('close',()=>{active.delete(toast);onClose();});
    toast.once('failed',()=>active.delete(toast));
    toast.show();return true;
  };
}
