import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('nvsAgent', {
  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: settings => ipcRenderer.invoke('settings:save', settings),
  login: settings => ipcRenderer.invoke('agent:login', settings),
  finishLogin: () => ipcRenderer.invoke('agent:finish-login'),
  checkSession: settings => ipcRenderer.invoke('agent:check-session', settings),
  start: settings => ipcRenderer.invoke('agent:start', settings),
  stop: () => ipcRenderer.invoke('agent:stop'),
  openFolder: () => ipcRenderer.invoke('agent:open-folder'),
  nvsStatus: settings => ipcRenderer.invoke('agent:nvs-status', settings),
  onLog: callback => ipcRenderer.on('agent-log', (_event, line) => callback(line)),
  onProcess: callback => ipcRenderer.on('agent-process', (_event, state) => callback(state)),
  onLogin: callback => ipcRenderer.on('agent-login', (_event, state) => callback(state)),
});
