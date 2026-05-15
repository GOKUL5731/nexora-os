/**
 * JARVIS Electron Preload — secure bridge between renderer and main process.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jarvis', {
  toggleCommandCenter: () => ipcRenderer.send('toggle-command-center'),
  hideWidget:          () => ipcRenderer.send('hide-widget'),
  minimizeWidget:      () => ipcRenderer.send('minimize-widget'),
  openExternal:        (url) => ipcRenderer.send('open-external', url),
  platform:            process.platform,
});
