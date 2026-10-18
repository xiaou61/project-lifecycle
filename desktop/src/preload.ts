// 渲染进程唯一的特权通道：只暴露固定几个方法，不暴露 ipcRenderer 或文件系统。
import { contextBridge, ipcRenderer } from "electron";

const api = {
  pickProject: () => ipcRenderer.invoke("pick-project") as Promise<string | null>,
  lastProject: () => ipcRenderer.invoke("last-project") as Promise<string | null>,
  listProjects: (root: string) => ipcRenderer.invoke("list-projects", root),
  loadWorkspace: (root: string) => ipcRenderer.invoke("load-workspace", root),
  forgetProject: (root: string) => ipcRenderer.invoke("forget-project", root) as Promise<void>,
  loadResources: (root: string) => ipcRenderer.invoke("load-resources", root),
  loadStatus: (root: string) => ipcRenderer.invoke("load-status", root),
  loadValidate: (root: string) => ipcRenderer.invoke("load-validate", root),
  loadHistory: (root: string) => ipcRenderer.invoke("load-history", root),
  loadArtifacts: (root: string, item: WorkItemView) =>
    ipcRenderer.invoke("load-artifacts", root, item),
  readDocument: (path: string) => ipcRenderer.invoke("read-document", path),
  revealInExplorer: (path: string) => ipcRenderer.invoke("reveal", path) as Promise<void>,
  openExternal: (url: string) => ipcRenderer.invoke("open-external", url) as Promise<void>,
};

contextBridge.exposeInMainWorld("api", api);
