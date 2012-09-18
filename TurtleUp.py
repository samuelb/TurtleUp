#!/usr/bin/python

VERSION = '0.9'
APPLIST = 'http://tracker/games.ini'

import os
import sys
import wx
import urllib
from ConfigParser import SafeConfigParser
import platform
import libtorrent
import time
from threading import Thread

applist_url = APPLIST
#applist_url = 'file://%s/games.ini' % os.getcwd()

ISWIN = platform.system() == 'Windows'
if ISWIN:
    import _winreg


state_str = ['queued', 'checking', 'downloading metastatus', 'downloading',
             'finished', 'finished/seeding', 'allocating', 'checking fastresume']


EVT_PROGRESS_ID = wx.NewId()


class UpdateProgressEvent(wx.PyEvent):
    
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_PROGRESS_ID)
        self.data = data


class UpdateProgress(Thread):

    def __init__(self, wxo, dl, app):
        Thread.__init__(self)
        self.wxo = wxo
        self.dl = dl
        self.app = app
        self.running = False
        self.start()
    
    def run(self):
        self.running = True
        #while not self.dl.is_seed() and self.running:
        while self.running:
            wx.PostEvent(self.wxo, UpdateProgressEvent((self.app, self.dl.status())))
            time.sleep(1)
        self.running = False

    def stop(self):
        self.running = False


class TurtleUp(wx.Frame):
 
    def __init__(self, parent, title, url):
        super(TurtleUp, self).__init__(parent, title=title, style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)
        
        try:
            self.apps = AppDB(url)
        except Exception, e:
            text = 'Failed to download App informations.\n\n%s' % e
            dlg = wx.MessageDialog(self, text, 'Damn!', wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            sys.exit(1)
        self.ResolvRegLookups()
        self.InitUI()
        self.InitBT()
        self.Centre()
        self.Show()
        
    def InitUI(self):
        self.SetSize((375, 300))
               
        boldFont = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT)
        boldFont.SetWeight(wx.BOLD)
                                      
        panel = wx.ScrolledWindow(self, -1, style=(wx.TAB_TRAVERSAL | wx.SUNKEN_BORDER))
        panel.SetScrollRate(10, 10)
        exitButton = wx.Button(self, 999, label='Exit')
                                                                              
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        listsizer = wx.BoxSizer(wx.VERTICAL)
                                                               
        mainsizer.Add(panel, 1, wx.EXPAND, 0)
        mainsizer.AddSpacer(5)
        mainsizer.Add(exitButton, 0, wx.ALIGN_RIGHT, 0)
       
        for app in self.apps.getAll():
            appBox = wx.StaticBox(panel, label=app['name'])
            appBox.SetFont(boldFont)
            appSizer = wx.StaticBoxSizer(appBox, wx.VERTICAL)
            tmpSizer = wx.BoxSizer(wx.HORIZONTAL)
            app['stat'] = wx.StaticText(panel, label=' ')
            app['gauge'] = wx.Gauge(panel, size=(250, 25))
            app['button'] = wx.Button(panel, app['id'], label='Start', size=(-1, 25))
            tmpSizer.Add(app['gauge'], -1, wx.RIGHT, 3)
            tmpSizer.Add(app['button'])
            appSizer.Add(tmpSizer)
            appSizer.Add(app['stat'])
            listsizer.Add(appSizer, -1, wx.ALL ^ wx.BOTTOM, 3)
            self.Bind(wx.EVT_BUTTON, self.OnStartStopButton, id=app['id'])
                                                                                                                                                                                   
            # diable uninstallable apps
            #if not self.IsInstallable(app):
            if app['dest'] is None and app['destreq']:
                app['button'].Enable(False)
                app['stat'].SetLabel(app['destreqtext'])
                app['stat'].SetForegroundColour(wx.RED)                                                                                                                                                                                                                                                                          
        self.SetSizer(mainsizer)
        panel.SetSizer(listsizer)
        
        self.Bind(wx.EVT_BUTTON, self.OnExit, id=999)
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.Connect(-1, -1, EVT_PROGRESS_ID, self.UpdateProgress)
        
    def OnExit(self, event):
        # TODO: stop torrents
        for app in self.apps.getAll():
            self.StopUpdate(app['id'])
        self.Destroy()
        sys.exit(0)
        
    def OnStartStopButton(self, event):
        button = event.GetEventObject()
        if button.GetLabel() == 'Start':
            try:
                if self.StartUpdate(button.GetId()):
                    button.SetLabel('Stop')
            except Exception, e:
                dlg = wx.MessageDialog(self, 'Something went wrong!\n\n%s' % e, 'Shit!', wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
        else:
            self.StopUpdate(button.GetId())
            button.SetLabel('Start')
        
    def InitBT(self):
        self.lt = libtorrent.session()
        self.lt.listen_on(6881, 6891)

    def StartUpdate(self, aid):
        app = self.apps.getFirst(id=aid)
        if app['dest'] == 'prompt':
            dlg = wx.DirDialog(self, 'Choose installation directory')
            ret = dlg.ShowModal()
            if ret == wx.ID_OK:
                app['dest'] = dlg.GetPath()
            else:
                dlg = wx.MessageDialog(self, 'You need to choose a valid installation directory', 'Oh no!', wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                return False
        if not os.path.exists(app['dest']) and app['destreq']:
            dlg = wx.MessageDialog(self, 'Install directory does not exist', 'Narf!', wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            return False
        tfp = urllib.urlopen(app['torrent'])
        tbdc = libtorrent.bdecode(tfp.read())
        tinfo = libtorrent.torrent_info(tbdc)
        app['download'] = self.lt.add_torrent(tinfo, app['dest'].encode('ASCII'))
        app['updater'] = UpdateProgress(self, app['download'], aid)
        return True
       
    def StopUpdate(self, aid):
        app = self.apps.getFirst(id=aid)
        if app.has_key('updater') and app['updater']:
            app['updater'].stop()
            app['updater'] = None
            app['stat'].SetLabel('stopped')
        if app.has_key('download'):
            # TODO: real check if torrent is active
            try:
                self.lt.remove_torrent(app['download'])
            except Exception:
                pass
        
    def UpdateProgress(self, event):
        aid, status = event.data
        app = self.apps.getFirst(id=aid)
        app['gauge'].SetValue(status.progress * 100)
        app['stat'].SetLabel('%s %d%% - down: %d kB/s up: %d kB/s peers: %d' %
            (state_str[status.state], status.progress * 100, status.download_rate / 1000, status.upload_rate / 1000, status.num_peers))
    
    #def IsInstallable(self, app):
    #    if app['destreq'] and not os.path.exists(app['dest']):
    #        return False
    #    return True
    
    def ResolvRegLookups(self):
        for app in self.apps.getAll():
            if app['dest'][:3].lower() == 'reg':
                if ISWIN:
                    try:
                        rp = app['dest'][4:].replace('/', '\\')
                        hkey, rp = rp.split('\\', 1)
                        rp, item = rp.rsplit('\\', 1)
                        r = _winreg.OpenKey(getattr(_winreg, hkey), rp)
                        app['dest'] = _winreg.QueryValueEx(r, item)[0]
                    except WindowsError:
                        app['dest'] = None
                else:
                    app['dest'] = None


class RATable():
    
    def __init__(self, data=[]):
        self.data = data
        
    def addApp(self, data):
        self.data.append(data)

    def getFirst(self, **kwargs):
        field = kwargs.keys()[0]
        for row in self.data:
            if row[field] == kwargs[field]:
                return row
    
    def getAll(self):
        return self.data
    
    def getAnd(self, **kwargs):
        result = []
        for row in self.data:
            flag = True
            for field in kwargs:
                if row[field] != kwargs[field]:
                    flag = False
                    break
            if flag:
                result.append(row)
        return result
                
    def getOr(self, **kwargs):
        result=[]
        for row in self.data:
            for field in kwargs:
                if row.has_key(field) and row[field] == kwargs[field]:
                    result.append(row)
                    break
        return result


class AppDB(RATable):
    
    def __init__(self, url=None):
        RATable.__init__(self)
        self.nextID = 0
        if url:
            self.readFromINI(url)
        
    def getID(self):
        nid = self.nextID
        self.nextID += 1
        return nid
        
    def readFromINI(self, url):
        cp = SafeConfigParser()
        fp = urllib.urlopen(url)
        cp.readfp(fp)
        for section in cp.sections():
            data = {'id': self.getID(),
                    'name': section,
                    'torrent': cp.get(section, 'torrent'),
                    'dest': cp.get(section, 'dest'),
                    'destreq': cp.getboolean(section, 'destreq'),
                    'destreqtext': cp.get(section, 'destreqtext'),
                    }
            self.addApp(data)


if __name__ == '__main__':
    app = wx.App()
    TurtleUp(None, 'TurtleUp %s' % VERSION, applist_url)
    app.MainLoop()
    
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
