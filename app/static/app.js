// ===== 提示通知 =====
function toast(msg, ok) {
  var el = document.createElement('div');
  el.className = 'toast ' + (ok ? 'ok' : 'err');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function() {
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    el.style.transition = 'all 0.2s ease';
    setTimeout(function(){ el.remove(); }, 200);
  }, 2800);
}

// ===== 仪表盘卡片入场动画 =====
document.addEventListener('DOMContentLoaded', function() {
  var cards = document.querySelectorAll('.config-card');
  cards.forEach(function(card, i) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(8px)';
    card.style.transition = 'all 0.3s ease';
    setTimeout(function() {
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 40 * i);
  });
});

// ===== 配置操作 =====
function cloneConfig(configId, name) {
  var newName = prompt('克隆为新配置 (修改名称):', name + '-clone');
  if (!newName) return;
  var data = new FormData();
  data.append('name', newName);
  fetch('/api/config/' + configId + '/clone', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) { toast('克隆成功: ' + d.message, true); setTimeout(function(){ location.reload(); }, 500); }
      else { toast(d.message || '克隆失败', false); }
    })
    .catch(function(e){ toast('错误: ' + e.message, false); });
}

function doAction(configId, action) {
  var actionNames = {start:'启动', stop:'停止', reread:'重读', enable:'开机自启', delete:'删除'};
  var name = actionNames[action] || action;
  if (action === 'delete' && !confirm('确定要删除这个配置吗？')) return;

  var form = new FormData();
  fetch('/api/config/' + configId + '/' + action, { method: 'POST', body: form })
    .then(function(r){ return r.json(); })
    .then(function(data){
      toast(data.message || (data.success ? name + '成功' : name + '失败'), data.success);
      if (data.success) setTimeout(function(){ location.reload(); }, 500);
    })
    .catch(function(e){ toast('错误: ' + e.message, false); });
}

// ===== 配置表单: 命令预览 =====
function updateCmdPreview() {
  var lmgrd = document.querySelector('input[name="lmgrd_path"]');
  var lic = document.querySelector('input[name="license_file"]');
  var log = document.querySelector('input[name="log_path"]');
  var extra = document.querySelector('input[name="extra_args"]');

  if (!lmgrd || !lic) return;
  var cmd = (lmgrd.value || 'lmgrd') + ' -c ' + (lic.value || '<license文件>');
  if (log && log.value) cmd += ' -l ' + log.value;
  if (extra && extra.value) cmd += ' ' + extra.value;
  var pre = document.getElementById('cmd-preview');
  if (pre) pre.textContent = '$ ' + cmd;
}

document.addEventListener('DOMContentLoaded', function(){
  var fields = document.querySelectorAll('input[name="lmgrd_path"], input[name="license_file"], input[name="log_path"], input[name="extra_args"]');
  fields.forEach(function(f){ f.addEventListener('input', updateCmdPreview); });
  updateCmdPreview();

  // 保存并启动按钮
  var saveStartBtn = document.getElementById('save-start-btn');
  if (saveStartBtn) {
    saveStartBtn.addEventListener('click', function(){
      var form = document.getElementById('config-form');
      if (!form) return;
      var data = new FormData(form);
      fetch('/api/config/save', { method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (d.success) {
            toast('已保存，正在启动...', true);
            return fetch('/api/config/' + d.config_id + '/start', { method: 'POST' });
          } else {
            throw new Error('保存失败');
          }
        })
        .then(function(r){ return r.json(); })
        .then(function(d){
          toast(d.message || '启动成功', d.success);
          if (d.success) setTimeout(function(){ window.location.href = '/'; }, 500);
        })
        .catch(function(e){ toast('错误: ' + e.message, false); });
    });
  }

  // 配置表单 AJAX 提交
  var configForm = document.getElementById('config-form');
  if (configForm) {
    configForm.addEventListener('submit', function(e){
      e.preventDefault();
      var data = new FormData(configForm);
      fetch('/api/config/save', { method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (d.success) {
            toast('配置已保存', true);
            setTimeout(function(){ window.location.href = '/'; }, 300);
          } else {
            toast(d.message || '保存失败', false);
          }
        })
        .catch(function(e){ toast('错误: ' + e.message, false); });
    });
  }

  // 文件浏览器: 路径输入框回车跳转
  var pathInput = document.getElementById('browser-path-input');
  if (pathInput) {
    pathInput.addEventListener('keydown', function(e){
      if (e.key === 'Enter') {
        var p = this.value.trim();
        if (p) loadBrowser(p);
      }
    });
  }

  // 文件浏览器按钮
  var browseBtns = document.querySelectorAll('.browse-btn');
  browseBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      var target = this.dataset.target;
      window._browseTarget = target;
      openBrowser('/');
    });
  });

  // 统计数据告警
  fetch('/api/stats')
    .then(function(r){ return r.json(); })
    .then(function(d){
      var el = document.getElementById('alert-count');
      if (el) el.textContent = d.alerts ? d.alerts.length : 0;
    });
});

// ===== 文件浏览器 =====
var _browseTarget = null;
var _browsePath = '/';
var _browseSelected = null;

function openBrowser(path) {
  loadBrowser(path || '/');
  _browseSelected = null;
  document.getElementById('browser-modal').classList.add('active');
  document.getElementById('browser-select-btn').disabled = true;
}

function closeBrowser() {
  document.getElementById('browser-modal').classList.remove('active');
}

function loadBrowser(path) {
  // Clean path: remove double slashes
  path = path.replace(/\/+/g, '/').replace(/\/$/, '') || '/';
  // Pass host_id if on config edit page
  var url = '/api/browse?path=' + encodeURIComponent(path);
  var hostSel = document.querySelector('select[name="host_id"]');
  if (hostSel && hostSel.value) url += '&host_id=' + hostSel.value;
  fetch(url)
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d.success) { toast(d.message, false); return; }
      _browsePath = d.path;
      document.getElementById('browser-path').textContent = d.path;
      var pathInput = document.getElementById('browser-path-input');
      if (pathInput) pathInput.value = d.path;
      var tbody = document.getElementById('browser-body');
      tbody.innerHTML = '';

      // 上级目录
      if (d.parent !== d.path) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td class="dir" colspan="3">📁 ..</td>';
        tr.onclick = function(){ loadBrowser(d.parent); };
        tbody.appendChild(tr);
      }

      d.entries.forEach(function(entry){
        var tr = document.createElement('tr');
        var icon = entry.is_dir ? '📁 ' : '📄 ';
        tr.innerHTML = '<td class="' + (entry.is_dir ? 'dir' : 'file') + '">' + icon + entry.name + '</td>' +
                       '<td class="size">' + (entry.is_dir ? '' : formatSize(entry.size)) + '</td>' +
                       '<td class="modified">' + entry.modified + '</td>';
        if (entry.is_dir) {
          tr.onclick = function(){ loadBrowser((d.path.replace(/\/+$/, '') || '') + '/' + entry.name); };
        } else {
          tr.onclick = function(e){
            var rows = tbody.querySelectorAll('tr');
            rows.forEach(function(r){ r.classList.remove('selected'); });
            tr.classList.add('selected');
            _browseSelected = (d.path.replace(/\/+$/, '') || '') + '/' + entry.name;
            document.getElementById('browser-select-btn').disabled = false;
          };
        }
        tbody.appendChild(tr);
      });
    });
}

function browseUp() {
  var parts = _browsePath.split('/').filter(Boolean);
  parts.pop();
  loadBrowser('/' + parts.join('/') || '/');
}

function filterBrowser() {
  var filter = document.getElementById('browser-filter').value.toLowerCase();
  var rows = document.getElementById('browser-body').querySelectorAll('tr');
  rows.forEach(function(row){
    var name = row.querySelector('.dir, .file');
    if (!name) return;
    row.style.display = name.textContent.toLowerCase().includes(filter) ? '' : 'none';
  });
}

function closeModal(id) {
  document.getElementById(id).classList.remove('active');
}

// 文件浏览器选择按钮
document.addEventListener('DOMContentLoaded', function(){
  var selectBtn = document.getElementById('browser-select-btn');
  if (selectBtn) {
    selectBtn.addEventListener('click', function(){
      if (_browseSelected && _browseTarget) {
        var target = document.querySelector(_browseTarget);
        if (target) {
          target.value = _browseSelected;
          // Trigger change event so preview fires
          target.dispatchEvent(new Event('change', { bubbles: true }));
          updateCmdPreview();
        }
      }
      closeBrowser();
    });
  }
  // 点击遮罩关闭弹窗
  document.querySelectorAll('.modal').forEach(function(m){
    m.addEventListener('click', function(e){ if (e.target === m) m.classList.remove('active'); });
  });
});

function formatSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ===== 日志页 =====
var _logPage = 0;
var _logLimit = 50;

function loadLogs(page) {
  _logPage = page || 0;
  fetch('/api/logs?limit=' + _logLimit + '&offset=' + (_logPage * _logLimit))
    .then(function(r){ return r.json(); })
    .then(function(d){
      var tbody = document.querySelector('#logs-table tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      if (d.logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">暂无日志记录。</td></tr>';
        return;
      }
      d.logs.forEach(function(log){
        tbody.innerHTML += '<tr>' +
          '<td>' + log.created_at + '</td>' +
          '<td>' + log.config_name + '</td>' +
          '<td>' + log.action + '</td>' +
          '<td class="' + (log.status === 'SUCCESS' ? 'log-status ok' : 'log-status fail') + '">' + (log.status === 'SUCCESS' ? '成功' : '失败') + '</td>' +
          '<td>' + (log.detail || '') + '</td>' +
          '</tr>';
      });
      var totalPages = Math.ceil(d.total / _logLimit);
      var pag = document.getElementById('log-pagination');
      if (pag) {
        pag.innerHTML = '';
        for (var i = 0; i < totalPages; i++) {
          var btn = document.createElement('button');
          btn.className = 'btn btn-sm ' + (i === _logPage ? 'btn-primary' : 'btn-outline');
          btn.textContent = i + 1;
          btn.onclick = (function(p){ return function(){ loadLogs(p); }; })(i);
          pag.appendChild(btn);
        }
      }
    });
}

if (document.getElementById('logs-table')) { loadLogs(0); }

// ===== 监控页 =====
var _monitorTimer = null;

function switchMonitorConfig() {
  refreshMonitor();
}

function refreshMonitor() {
  var sel = document.getElementById('monitor-config-select');
  var configId = sel ? sel.value : null;
  if (!configId) return;

  fetch('/api/config/' + configId + '/lmstat')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d.success) { toast(d.message, false); return; }
      renderFeatures(d.features, configId);
    });
}

function renderFeatures(features, configId) {
  var tbody = document.getElementById('feature-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  var totalLic = 0, totalUsed = 0;

  features.forEach(function(f, i){
    totalLic += f.total;
    totalUsed += f.used;
    var pct = f.total > 0 ? Math.round(f.used / f.total * 100) : 0;
    var barColor = pct >= 90 ? 'var(--red)' : pct >= 70 ? 'var(--yellow)' : 'var(--green)';
    tbody.innerHTML += '<tr>' +
      '<td>' + (i + 1) + '</td>' +
      '<td class="clickable" onclick="showUsers(' + configId + ', \'' + f.feature + '\')">' + f.feature + '</td>' +
      '<td>' + (f.vendor || '-') + '</td>' +
      '<td>' + (f.version || '-') + '</td>' +
      '<td>' + f.total + '</td>' +
      '<td>' + f.used + '</td>' +
      '<td><span class="usage-bar-bg"><span class="usage-bar" style="width:' + pct + 'px; background:' + barColor + ';"></span></span> ' + pct + '%</td>' +
      '</tr>';
  });

  if (features.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">未发现功能或许可证未运行。</td></tr>';
  }

  document.getElementById('monitor-summary').style.display = features.length ? 'flex' : 'none';
  document.getElementById('sum-features').textContent = features.length;
  document.getElementById('sum-total').textContent = totalLic;
  document.getElementById('sum-used').textContent = totalUsed;
  document.getElementById('sum-rate').textContent = totalLic > 0 ? Math.round(totalUsed / totalLic * 100) + '%' : '0%';
}

function showUsers(configId, feature) {
  fetch('/api/config/' + configId + '/lmstat/users/' + encodeURIComponent(feature))
    .then(function(r){ return r.json(); })
    .then(function(d){
      document.getElementById('user-feature-name').textContent = feature;
      var tbody = document.getElementById('user-table-body');
      tbody.innerHTML = '';
      if (!d.success || !d.users || d.users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">无用户或无法解析。</td></tr>';
      } else {
        d.users.forEach(function(u){
          tbody.innerHTML += '<tr><td>' + u.user + '</td><td>' + u.host + '</td><td>' + u.display + '</td><td>' + u.version + '</td></tr>';
        });
      }
      document.getElementById('user-modal').classList.add('active');
    });
}

function toggleAutoRefresh() {
  if (document.getElementById('auto-refresh').checked) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
}

function setRefreshInterval() {
  if (document.getElementById('auto-refresh').checked) {
    stopAutoRefresh();
    startAutoRefresh();
  }
}

function startAutoRefresh() {
  var interval = parseInt(document.getElementById('refresh-interval').value) || 5;
  _monitorTimer = setInterval(refreshMonitor, interval * 1000);
}

function stopAutoRefresh() {
  if (_monitorTimer) { clearInterval(_monitorTimer); _monitorTimer = null; }
}

// ===== 厂商管理 =====
function editVendor(id, daemon, name, path, exclude, hostId) {
  document.getElementById('vendor-edit-id').value = id;
  document.getElementById('vendor-edit-daemon').value = daemon;
  document.getElementById('vendor-edit-vname').value = name;
  document.getElementById('vendor-edit-path').value = path || '';
  document.getElementById('vendor-edit-exclude').value = exclude || '';
  // Populate host dropdown
  var hostSel = document.getElementById('vendor-edit-host');
  if (hostSel) {
    // Copy options from the add form's host selector
    var addHostSel = document.getElementById('vendor-host');
    if (addHostSel) {
      hostSel.innerHTML = addHostSel.innerHTML;
      if (hostId) hostSel.value = hostId;
    }
  }
  document.getElementById('vendor-edit-title').textContent = '编辑厂商';
  document.getElementById('vendor-edit-modal').classList.add('active');
}

function saveVendorModal() {
  var data = new FormData(document.getElementById('vendor-edit-form'));
  fetch('/api/vendors/save', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) { closeModal('vendor-edit-modal'); toast('厂商已保存', true); setTimeout(function(){ location.reload(); }, 300); }
      else { toast(d.message || '保存失败', false); }
    });
}

function resetVendorForm() {
  document.getElementById('vendor-form').reset();
  document.getElementById('vendor-form-title').textContent = '添加厂商';
  document.getElementById('vendor-id').value = '';
}

function deleteVendor(id) {
  if (!confirm('确定要删除这个厂商吗？')) return;
  var form = new FormData();
  fetch('/api/vendors/' + id + '/delete', { method: 'POST', body: form })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) { toast('厂商已删除', true); setTimeout(function(){ location.reload(); }, 300); }
      else { toast(d.message || '删除失败', false); }
    });
}

document.addEventListener('DOMContentLoaded', function(){
  var vendorForm = document.getElementById('vendor-form');
  if (vendorForm) {
    vendorForm.addEventListener('submit', function(e){
      e.preventDefault();
      var data = new FormData(vendorForm);
      var id = document.getElementById('vendor-id').value;
      if (id) data.append('id', id);
      fetch('/api/vendors/save', { method: 'POST', body: data })
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (d.success) { toast('厂商已保存', true); setTimeout(function(){ location.reload(); }, 300); }
          else { toast(d.message || '保存失败', false); }
        });
    });
  }

  // 监控页自动加载
  if (document.getElementById('feature-table') && document.getElementById('monitor-config-select')) {
    var cid = document.getElementById('monitor-config-select').value;
    if (cid) refreshMonitor();
  }
});

// ===== 快速添加厂商 (配置页) =====
function quickAddVendor() {
  var el = document.getElementById('quick-vendor-form');
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function saveQuickVendor() {
  var daemon = document.getElementById('quick-daemon').value.trim();
  var name = document.getElementById('quick-vendor-name').value.trim();
  var path = document.getElementById('quick-daemon-path').value.trim();
  if (!daemon || !name) { toast('Daemon 名称和厂商名称必填', false); return; }

  var data = new FormData();
  data.append('daemon_name', daemon);
  data.append('vendor_name', name);
  data.append('default_daemon_path', path);

  fetch('/api/vendors/save', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) {
        toast('厂商已添加', true);
        setTimeout(function(){ location.reload(); }, 300);
      } else {
        toast(d.message || '添加失败', false);
      }
    });
}

// ===== Web 终端 =====
function initTerminal() {
  var container = document.getElementById('terminal-container');
  if (!container) return;

  container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);">正在加载终端组件...</div>';

  // 加载 xterm.js CSS
  var css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css';
  css.onerror = function() {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);">无法加载 xterm 样式 (CDN 不可达)</div>';
  };
  document.head.appendChild(css);

  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js';
  script.onerror = function() {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--red);">无法加载 xterm.js (CDN 不可达)</div>';
  };
  script.onload = function() {
    container.innerHTML = '';
    var term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      theme: {
        background: '#1a1b26',
        foreground: '#c0caf5',
        cursor: '#7aa2f7',
        selectionBackground: '#26283b'
      },
      allowProposedApi: true
    });
    term.open(container);
    term.focus();

    // socket.io 已在 terminal.html 中通过 script 标签加载，全局 io() 可用
    if (typeof io === 'undefined') {
      term.writeln('\r\n\x1b[31mSocket.IO 未加载，请刷新页面重试\x1b[0m');
      return;
    }

    var socket = io();

    socket.on('connect', function() {
      term.writeln('\r\n\x1b[32m已连接到服务器\x1b[0m\r\n');
      socket.emit('terminal-init');
    });

    socket.on('connect_error', function() {
      term.writeln('\r\n\x1b[31m连接失败，正在重试...\x1b[0m');
    });

    socket.on('terminal-output', function(data) {
      term.write(data);
    });

    term.onData(function(data) {
      socket.emit('terminal-input', data);
    });

    term.onResize(function(size) {
      socket.emit('terminal-resize', { rows: size.rows, cols: size.cols });
    });

    window.addEventListener('beforeunload', function() {
      socket.disconnect();
    });
  };
  document.body.appendChild(script);
}

if (document.getElementById('terminal-container')) {
  initTerminal();
}

// ===== 日志查看器 (tail -f) =====
function initLogViewer() {
  var logContent = document.getElementById('log-content');
  if (!logContent) return;

  var pathMatch = window.location.pathname.match(/\/config\/(\d+)\/log/);
  if (!pathMatch) return;
  var configId = pathMatch[1];

  // 先加载已有内容
  fetch('/api/config/' + configId + '/log/content?lines=200')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) {
        logContent.textContent = d.content;
        scrollToBottom();
      } else {
        logContent.textContent = d.message;
      }
    })
    .catch(function(e){
      logContent.textContent = '加载失败: ' + e.message;
    });

  // 建立 SSE 连接获取实时内容
  var evtSource = null;
  var pendingLines = [];
  window._logPaused = false;

  function connectSSE() {
    if (evtSource) evtSource.close();
    evtSource = new EventSource('/api/config/' + configId + '/log/tail');

    evtSource.onmessage = function(event) {
      if (window._logPaused) {
        pendingLines.push(event.data);
      } else {
        logContent.textContent += event.data;
        scrollToBottom();
      }
    };

    evtSource.onerror = function() {
      // 连接断开，5秒后重试
      evtSource.close();
      setTimeout(connectSSE, 5000);
    };
  }

  connectSSE();

  window.togglePause = function() {
    window._logPaused = !window._logPaused;
    var btn = document.getElementById('pause-btn');
    if (window._logPaused) {
      btn.innerHTML = '&#9654; 继续';
      btn.classList.add('btn-success');
    } else {
      btn.innerHTML = '&#9646;&#9646; 暂停';
      btn.classList.remove('btn-success');
      if (pendingLines.length > 0) {
        logContent.textContent += pendingLines.join('');
        pendingLines = [];
        scrollToBottom();
      }
    }
  };

  window.scrollToBottom = function() {
    var container = document.getElementById('log-container');
    if (container) container.scrollTop = container.scrollHeight;
  };

  window.clearLog = function() {
    logContent.textContent = '';
    pendingLines = [];
  };

  window.addEventListener('beforeunload', function() {
    if (evtSource) evtSource.close();
  });
}

if (document.getElementById('log-container')) {
  initLogViewer();
}

// ===== 厂商切换自动填充 daemon 路径和 exclude =====
function onVendorChange() {
  var sel = document.getElementById('vendor-select');
  if (!sel) return;
  var opt = sel.options[sel.selectedIndex];
  var daemonPath = opt.getAttribute('data-daemon-path') || '';
  var excludePath = opt.getAttribute('data-exclude-path') || '';

  var dpInput = document.querySelector('input[name="daemon_path"]');
  if (dpInput && !dpInput.value && daemonPath) {
    dpInput.value = daemonPath;
  }

  var ofInput = document.querySelector('input[name="options_file"]');
  if (ofInput && !ofInput.value && excludePath) {
    ofInput.value = excludePath;
  }

  updateCmdPreview();
}

// ===== License 文件预览 =====
function previewLicense(path) {
  var pre = document.getElementById('license-preview');
  if (!pre || !path) {
    if (pre) pre.textContent = '选择 license 文件后自动显示';
    return;
  }
  pre.textContent = '加载中...';
  var data = new FormData();
  data.append('path', path);
  var hostSel = document.querySelector('select[name="host_id"]');
  if (hostSel && hostSel.value) data.append('host_id', hostSel.value);
  fetch('/api/config/license-preview', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      pre.textContent = d.content || '(空文件)';
    })
    .catch(function(e){
      pre.textContent = '加载失败: ' + e.message;
    });
}

// ===== 端口检测 =====
function checkPort() {
  var pathMatch = window.location.pathname.match(/\/config\/(\d+)\/edit/);
  var configId = pathMatch ? pathMatch[1] : null;
  if (!configId) { toast('请先保存配置', false); return; }

  var result = document.getElementById('port-check-result');
  result.innerHTML = '<span style="color:var(--text-dim);">端口检测中...</span>';

  fetch('/api/config/' + configId + '/port-check')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) {
        var color = d.listening ? 'var(--green)' : 'var(--red)';
        result.innerHTML = '<div style="color:' + color + ';">端口 ' + d.port + ': ' + (d.listening ? '已监听' : '未监听') + '</div>';
      } else {
        result.innerHTML = '<span style="color:var(--yellow);">' + d.message + '</span>';
      }
    })
    .catch(function(e){
      result.innerHTML = '<span style="color:var(--red);">检测失败: ' + e.message + '</span>';
    });
}

// ===== 主机管理 =====
function editHost(id, name, hostname, port, username) {
  document.getElementById('host-edit-id').value = id;
  document.getElementById('host-edit-name').value = name;
  document.getElementById('host-edit-hostname').value = hostname;
  document.getElementById('host-edit-port').value = port;
  document.getElementById('host-edit-username').value = username;
  document.getElementById('host-edit-password').value = '';
  document.getElementById('host-edit-title').textContent = '编辑主机';
  document.getElementById('host-edit-modal').classList.add('active');
}

function saveHostModal() {
  var data = new FormData(document.getElementById('host-edit-form'));
  fetch('/api/hosts/save', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) { closeModal('host-edit-modal'); toast('主机已保存', true); setTimeout(function(){ location.reload(); }, 300); }
      else { toast(d.message || '保存失败', false); }
    });
}

function resetHostForm() {
  document.getElementById('host-form').reset();
  document.getElementById('host-form-title').textContent = '添加主机';
  document.getElementById('host-id').value = '';
}

function deleteHost(id) {
  if (!confirm('确定要删除这个主机吗？')) return;
  var form = new FormData();
  fetch('/api/hosts/' + id + '/delete', { method: 'POST', body: form })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) { toast('主机已删除', true); setTimeout(function(){ location.reload(); }, 300); }
      else { toast(d.message || '删除失败', false); }
    });
}

function testHost(id) {
  var btn = event.target;
  btn.textContent = '测试中...';
  btn.disabled = true;
  fetch('/api/hosts/' + id + '/test', { method: 'POST' })
    .then(function(r){ return r.json(); })
    .then(function(d){
      toast(d.message, d.success);
      // Update status badge without reloading
      var card = document.getElementById('host-' + id);
      if (card) {
        var badge = card.querySelector('.host-status');
        if (badge) {
          badge.textContent = d.success ? 'online' : 'offline';
          badge.className = 'host-status ' + (d.success ? 'online' : 'offline');
        }
      }
    })
    .catch(function(e){ toast('错误: ' + e.message, false); })
    .finally(function(){ btn.textContent = '测试连接'; btn.disabled = false; });
}

document.addEventListener('DOMContentLoaded', function(){
  var hostForm = document.getElementById('host-form');
  if (hostForm) {
    hostForm.addEventListener('submit', function(e){
      e.preventDefault();
      var data = new FormData(hostForm);
      data.append('auth_type', 'password');
      fetch('/api/hosts/save', { method: 'POST', body: data })
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (d.success) { toast('主机已添加', true); setTimeout(function(){ location.reload(); }, 300); }
          else { toast(d.message || '保存失败', false); }
        });
    });
  }

  // 全局设置保存
  var settingsForm = document.getElementById('settings-form');
  if (settingsForm) {
    settingsForm.addEventListener('submit', function(e){
      e.preventDefault();
      var data = new FormData(settingsForm);
      fetch('/api/settings/save', { method: 'POST', body: data })
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (d.success) { toast('设置已保存', true); }
          else { toast(d.message || '保存失败', false); }
        });
    });
  }

  // 厂商切换触发
  var vendorSel = document.getElementById('vendor-select');
  if (vendorSel) onVendorChange();

  // 主机切换触发 SERVER hostname 更新
  var hostSel = document.getElementById('host-select');
  if (hostSel) {
    hostSel.addEventListener('change', function(){
      updateServerHostname();
    });
    updateServerHostname();
  }
});

// ===== Backup / Restore =====
function exportBackup() {
  var btn = event.target;
  var origText = btn.textContent;
  btn.textContent = '导出中...';
  btn.disabled = true;
  fetch('/api/backup/export')
    .then(function(r){ return r.json(); })
    .then(function(data){
      var blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'licman-backup-' + new Date().toISOString().slice(0,10) + '.json';
      a.click();
      URL.revokeObjectURL(url);
      toast('备份已导出', true);
    })
    .catch(function(e){ toast('导出失败: ' + e.message, false); })
    .finally(function(){ btn.textContent = origText; btn.disabled = false; });
}

function importBackup() {
  var fileInput = document.getElementById('backup-file');
  var file = fileInput.files[0];
  if (!file) return;
  var result = document.getElementById('backup-result');
  result.innerHTML = '<span style="color:var(--text-dim);">导入中...</span>';

  var data = new FormData();
  data.append('file', file);
  data.append('mode', document.getElementById('import-mode').value);
  fetch('/api/backup/import', { method: 'POST', body: data })
    .then(function(r){ return r.json(); })
    .then(function(d){
      result.innerHTML = '<span style="color:' + (d.success ? 'var(--green)' : 'var(--red)') + ';">' + d.message + '</span>';
      if (d.success) toast('还原成功', true);
    })
    .catch(function(e){
      result.innerHTML = '<span style="color:var(--red);">导入失败: ' + e.message + '</span>';
    });
  fileInput.value = '';
}

// ===== 用量快照 =====
function snapshotUsage() {
  var btn = event ? event.target : document.querySelector('#snapshot-btn');
  var origText = btn ? btn.textContent : '记录中...';
  if (btn) { btn.textContent = '记录中...'; btn.disabled = true; }
  fetch('/api/usage/snapshot')
    .then(function(r){ return r.json(); })
    .then(function(d){
      toast(d.message, d.success);
      if (d.success && typeof loadTrends === 'function') loadTrends();
    })
    .finally(function(){ if (btn) { btn.textContent = origText; btn.disabled = false; } });
}

// ===== 邮件测试 =====
function testNotify() {
  var result = document.getElementById('notify-result');
  if (result) result.innerHTML = '<span style="color:var(--text-dim);">发送中...</span>';
  fetch('/api/notify/test', { method: 'POST' })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (result) result.innerHTML = '<span style="color:' + (d.success ? 'var(--green)' : 'var(--red)') + ';">' + d.message + '</span>';
      else toast(d.message, d.success);
    });
}

function updateServerHostname() {
  var sel = document.getElementById('host-select');
  var hint = document.getElementById('server-hostname-hint');
  var preview = document.getElementById('server-hostname-preview');
  var val = document.getElementById('server-hostname-value');
  if (!sel || !hint) return;
  var opt = sel.options[sel.selectedIndex];
  var hostname = opt.getAttribute('data-hostname') || '';
  if (hostname) {
    hint.style.display = '';
    if (preview) preview.textContent = hostname;
    if (val) val.value = hostname;
  } else {
    hint.style.display = 'none';
    if (val) val.value = '';
  }
}

// ===== DAEMON 行检测 =====
function checkDaemonLine() {
  var pathMatch = window.location.pathname.match(/\/config\/(\d+)\/edit/);
  var configId = pathMatch ? pathMatch[1] : null;
  if (!configId) {
    // New config - no license file yet
    toast('请先保存配置再检测 DAEMON 行', false);
    return;
  }

  var result = document.getElementById('daemon-check-result');
  result.innerHTML = '<span style="color:var(--text-dim);">检测中...</span>';

  fetch('/api/config/' + configId + '/daemon-check')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (!d.success) {
        result.innerHTML = '<span style="color:var(--red);">' + d.message + '</span>';
        return;
      }

      var html = '<div style="font-size:11px;">';
      html += '<div style="color:var(--blue);margin-bottom:6px;">DAEMON 行检测结果:</div>';

      if (d.line_number === null) {
        html += '<div style="color:var(--red);">未找到 DAEMON 行</div>';
      } else {
        html += '<div style="color:var(--text-dim);margin-bottom:4px;">行号: ' + (d.line_number + 1) + '</div>';
        html += '<div style="color:var(--text-dim);margin-bottom:4px;">当前行: <code style="color:var(--text);">' + (d.daemon_line || '').trim() + '</code></div>';

        // Col 3 (daemon path)
        if (d.col3_conflict) {
          html += '<div style="color:var(--yellow);margin:4px 0;">&#9888; 第3列(daemon路径)冲突:</div>';
          html += '<div style="margin-left:8px;color:var(--text-dim);">原值: ' + d.current_col3 + '</div>';
          html += '<div style="margin-left:8px;color:var(--text-dim);">新值: ' + (d.current_col3 || '') + '</div>';
        } else if (d.col3_empty) {
          html += '<div style="color:var(--text-dim);margin:4px 0;">第3列(daemon路径): 为空,将自动填入</div>';
        } else {
          html += '<div style="color:var(--green);margin:4px 0;">第3列(daemon路径): 已匹配</div>';
        }

        // Col 4 (exclude file)
        if (d.col4_conflict) {
          html += '<div style="color:var(--yellow);margin:4px 0;">&#9888; 第4列(exclude文件)冲突:</div>';
          html += '<div style="margin-left:8px;color:var(--text-dim);">原值: ' + d.current_col4 + '</div>';
          html += '<div style="margin-left:8px;color:var(--text-dim);">新值: ' + (d.current_col4 || '') + '</div>';
        } else if (d.col4_empty) {
          html += '<div style="color:var(--text-dim);margin:4px 0;">第4列(exclude文件): 为空,将自动填入</div>';
        } else {
          html += '<div style="color:var(--green);margin:4px 0;">第4列(exclude文件): 已匹配</div>';
        }

        if (d.col3_conflict || d.col4_conflict) {
          html += '<button class="btn btn-sm btn-warning" style="margin-top:8px;" onclick="forceDaemonWrite(' + configId + ')">强制写入 (覆盖原值)</button>';
        } else if (d.col3_empty || d.col4_empty) {
          html += '<button class="btn btn-sm btn-primary" style="margin-top:8px;" onclick="forceDaemonWrite(' + configId + ')">写入 DAEMON 行</button>';
        }
      }

      html += '</div>';
      result.innerHTML = html;
    })
    .catch(function(e){
      result.innerHTML = '<span style="color:var(--red);">检测失败: ' + e.message + '</span>';
    });
}

function forceDaemonWrite(configId) {
  var result = document.getElementById('daemon-check-result');
  result.innerHTML = '<span style="color:var(--text-dim);">写入中...</span>';

  fetch('/api/config/' + configId + '/daemon-write', { method: 'POST' })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.success) {
        result.innerHTML = '<span style="color:var(--green);">' + d.message + '</span>';
      } else {
        result.innerHTML = '<span style="color:var(--red);">' + d.message + '</span>';
      }
    })
    .catch(function(e){
      result.innerHTML = '<span style="color:var(--red);">写入失败: ' + e.message + '</span>';
    });
}
