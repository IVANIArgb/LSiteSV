;(function () {
  async function fetchCurrentUser() {
    try {
      const resp = await fetch('/api/current-user', { credentials: 'include' })
      if (!resp.ok) return null
      const data = await resp.json().catch(() => null)
      return data && typeof data === 'object' ? data : null
    } catch (e) {
      console.error('Не удалось получить текущего пользователя', e)
      return null
    }
  }

  async function fetchCurrentContentRootInfo() {
    try {
      const resp = await fetch('/api/admin/content-root', {
        method: 'GET',
        credentials: 'include',
      })
      if (!resp.ok) return null
      const data = await resp.json().catch(() => null)
      return data && typeof data === 'object' ? data : null
    } catch (e) {
      console.error('Не удалось получить информацию о папке контента', e)
      return null
    }
  }

  async function applyContentRootPath(path) {
    const resp = await fetch('/api/admin/content-root', {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok || !data || data.ok !== true) {
      const msg =
        (data && data.error) ||
        `Не удалось обновить папку контента (код ${resp.status}). Проверьте путь и права доступа.`
      throw new Error(msg)
    }
    return data
  }

  function closeFolderPicker(overlay) {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay)
  }

  async function loadFolderListing(path) {
    const url = path
      ? '/api/admin/content-root/browse?path=' + encodeURIComponent(path)
      : '/api/admin/content-root/browse'
    const resp = await fetch(url, { credentials: 'include' })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      throw new Error((data && data.error) || 'Не удалось прочитать папки')
    }
    return data
  }

  async function openFolderPicker(startPath) {
    return new Promise(function (resolve) {
      const overlay = document.createElement('div')
      overlay.className = 'folder-picker-overlay'
      overlay.innerHTML =
        '<div class="folder-picker" role="dialog" aria-modal="true" aria-labelledby="folder-picker-title">' +
        '<h2 id="folder-picker-title">Выбор папки контента</h2>' +
        '<p class="folder-picker-hint">Браузер не может открыть проводник Windows. Ниже — папки на этом компьютере (сервер LearningSite).</p>' +
        '<div class="folder-picker-path" id="folder-picker-current"></div>' +
        '<div class="folder-picker-toolbar">' +
        '<button type="button" class="folder-picker-btn" id="folder-picker-up">На уровень выше</button>' +
        '<button type="button" class="folder-picker-btn" id="folder-picker-home">Диски / корень</button>' +
        '</div>' +
        '<ul class="folder-picker-list" id="folder-picker-list"></ul>' +
        '<label class="folder-picker-manual">Или введите путь вручную' +
        '<input type="text" id="folder-picker-input" autocomplete="off" spellcheck="false">' +
        '</label>' +
        '<div class="folder-picker-actions">' +
        '<button type="button" class="folder-picker-btn folder-picker-btn--ghost" id="folder-picker-cancel">Отмена</button>' +
        '<button type="button" class="folder-picker-btn folder-picker-btn--primary" id="folder-picker-go">Перейти</button>' +
        '<button type="button" class="folder-picker-btn folder-picker-btn--primary" id="folder-picker-ok">Выбрать эту папку</button>' +
        '</div>' +
        '<p class="folder-picker-status" id="folder-picker-status"></p>' +
        '</div>'

      document.body.appendChild(overlay)

      const currentEl = overlay.querySelector('#folder-picker-current')
      const listEl = overlay.querySelector('#folder-picker-list')
      const inputEl = overlay.querySelector('#folder-picker-input')
      const statusEl = overlay.querySelector('#folder-picker-status')
      const upBtn = overlay.querySelector('#folder-picker-up')
      let listing = { current: startPath || '', parent: null, entries: [], is_drives: false }

      function setStatus(text) {
        statusEl.textContent = text || ''
      }

      function render() {
        currentEl.textContent = listing.is_drives
          ? 'Диски этого компьютера'
          : listing.current || '—'
        inputEl.value = listing.current || ''
        upBtn.disabled = listing.parent === null && !listing.is_drives
        listEl.innerHTML = ''
        ;(listing.entries || []).forEach(function (entry) {
          const li = document.createElement('li')
          const btn = document.createElement('button')
          btn.type = 'button'
          btn.className = 'folder-picker-item'
          btn.textContent = entry.name
          btn.addEventListener('click', function () {
            refresh(entry.path)
          })
          li.appendChild(btn)
          listEl.appendChild(li)
        })
        if (!(listing.entries || []).length) {
          const li = document.createElement('li')
          li.className = 'folder-picker-empty'
          li.textContent = listing.error || 'В этой папке нет подпапок'
          listEl.appendChild(li)
        }
      }

      async function refresh(path) {
        setStatus('Загрузка…')
        try {
          listing = await loadFolderListing(path)
          setStatus(listing.error || '')
          render()
        } catch (err) {
          setStatus(err.message || String(err))
        }
      }

      overlay.querySelector('#folder-picker-cancel').addEventListener('click', function () {
        closeFolderPicker(overlay)
        resolve(null)
      })
      overlay.addEventListener('click', function (ev) {
        if (ev.target === overlay) {
          closeFolderPicker(overlay)
          resolve(null)
        }
      })
      upBtn.addEventListener('click', function () {
        if (listing.is_drives) return
        if (listing.parent === '') refresh('')
        else if (listing.parent) refresh(listing.parent)
      })
      overlay.querySelector('#folder-picker-home').addEventListener('click', function () {
        refresh('')
      })
      overlay.querySelector('#folder-picker-go').addEventListener('click', function () {
        refresh((inputEl.value || '').trim())
      })
      overlay.querySelector('#folder-picker-ok').addEventListener('click', function () {
        const chosen = (inputEl.value || listing.current || '').trim()
        if (!chosen) {
          setStatus('Сначала откройте папку или введите путь')
          return
        }
        closeFolderPicker(overlay)
        resolve(chosen)
      })

      refresh(startPath || '')
    })
  }

  async function handleChangeContentRootClick() {
    const info = await fetchCurrentContentRootInfo()
    const startPath = info && info.current_root ? info.current_root : ''
    const path = await openFolderPicker(startPath)
    if (!path) return

    try {
      const data = await applyContentRootPath(path)
      const finalMsg =
        'Папка контента обновлена.\n\n' +
        (data.new_root || path) +
        '\n\nПри необходимости перезапустите сервер, если страницы ещё показывают старые курсы.'
      if (window.customAlert) {
        await window.customAlert(finalMsg, 'Готово')
      } else {
        alert(finalMsg)
      }
    } catch (e) {
      const msg = e && e.message ? e.message : String(e)
      if (window.customAlert) {
        await window.customAlert(msg, 'Ошибка смены папки контента')
      } else {
        alert(msg)
      }
    }
  }

  function initChangeContentRootButton(user) {
    const allowed =
      user &&
      (user.can_manage_content_root === true ||
        (user.effective_role || user.role || '').toLowerCase() === 'super_admin')
    if (!allowed) {
      return
    }

    const menuList = document.getElementById('admin-menu-list') || document.querySelector('.menu ul')
    if (!menuList) return

    const li = document.createElement('li')
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'menu-change-content-btn'
    btn.textContent = 'Сменить папку контента'
    btn.addEventListener('click', handleChangeContentRootClick)

    li.appendChild(btn)
    menuList.appendChild(li)
  }

  function applyMenuBadges(overview) {
    if (!overview) return
    var qBadge = document.getElementById('menu-badge-questions')
    var binBadge = document.getElementById('menu-badge-bin')
    var qCount = Number(overview.open_questions) || 0
    var binCount = Number(overview.bin_count) || 0
    if (qBadge) {
      if (qCount > 0) {
        qBadge.hidden = false
        qBadge.textContent = qCount > 99 ? '99+' : String(qCount)
      } else {
        qBadge.hidden = true
      }
    }
    if (binBadge) {
      if (binCount > 0) {
        binBadge.hidden = false
        binBadge.textContent = binCount > 99 ? '99+' : String(binCount)
      } else {
        binBadge.hidden = true
      }
    }
  }

  function studentsLabel(count) {
    var n = Number(count) || 0
    var mod10 = n % 10
    var mod100 = n % 100
    if (mod10 === 1 && mod100 !== 11) return n + ' студент'
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return n + ' студента'
    return n + ' студентов'
  }

  function renderList(listEl, items, buildItem) {
    if (!listEl) return
    if (!items || !items.length) {
      listEl.innerHTML = '<li class="dashboard-empty">Пока нет данных</li>'
      return
    }
    listEl.innerHTML = items.map(buildItem).join('')
  }

  async function loadAdminDashboardFallback() {
    var coursesResp = await fetch('/api/courses?per_page=200', { credentials: 'include' })
    var statsResp = await fetch('/api/statistics', { credentials: 'include' })
    var newsResp = await fetch('/api/news?limit=12', { credentials: 'include' })
    var questionsResp = await fetch('/api/questions/unanswered-count', { credentials: 'include' })

    if (!coursesResp.ok && !statsResp.ok) {
      throw new Error('fallback failed')
    }

    var activeCourses = []
    if (coursesResp.ok) {
      var coursesData = await coursesResp.json()
      activeCourses = (coursesData.courses || []).map(function (course) {
        return {
          title: course.title,
          category_title: course.category_title || '',
          href: '/all-lessons-pg?course_id=' + course.id,
          students_count: 0,
          students_label: '',
        }
      })
    }

    var courseStats = []
    var overview = {}
    if (statsResp.ok) {
      var statsData = await statsResp.json()
      overview = statsData.overview || {}
      courseStats = (statsData.courses || [])
        .slice()
        .sort(function (a, b) {
          return (b.enrolled_users || 0) - (a.enrolled_users || 0)
        })
        .map(function (course) {
          return {
            title: course.course_title,
            students_count: course.enrolled_users || 0,
            href: '/all-lessons-pg?course_id=' + course.course_id,
          }
        })
    }

    var notifications = []
    var qCount = 0
    if (questionsResp.ok) {
      var qData = await questionsResp.json()
      qCount = Number(qData.count) || 0
      if (qCount > 0) {
        notifications.push({
          kind: 'alert',
          label: 'Вопросы',
          title: qCount + ' открытых',
          subtitle: 'Пользователи ждут ответа — перейдите в раздел вопросов.',
          href: '/questions',
          time: '',
        })
      }
    }
    if (newsResp.ok) {
      var newsData = await newsResp.json()
      ;(newsData.events || []).forEach(function (ev) {
        notifications.push({
          kind: 'news',
          label: 'Событие',
          title: ev.title,
          subtitle: ev.body ? String(ev.body).slice(0, 120) : 'Изменение на платформе.',
          href: '/main',
          time: ev.created_at ? formatWhen(ev.created_at) : '',
        })
      })
    }
    if (!notifications.length) {
      notifications.push({
        kind: 'system',
        label: 'Система',
        title: 'Всё спокойно',
        subtitle: 'Нет срочных задач. Журнал — в разделе «Логи».',
        href: '/logs',
        time: '',
      })
    }

    overview.open_questions = qCount

    return {
      active_courses: activeCourses,
      notifications: notifications,
      course_stats: courseStats,
      overview: overview,
    }
  }

  function formatWhen(iso) {
    if (!iso) return ''
    var dt = new Date(iso)
    if (isNaN(dt.getTime())) return ''
    var diff = Date.now() - dt.getTime()
    if (diff < 60000) return 'только что'
    if (diff < 3600000) return Math.floor(diff / 60000) + ' мин. назад'
    if (diff < 86400000) return Math.floor(diff / 3600000) + ' ч. назад'
    if (diff < 172800000) return 'вчера'
    if (diff < 604800000) return Math.floor(diff / 86400000) + ' дн. назад'
    return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  function notifyClass(kind) {
    if (kind === 'alert') return 'dashboard-notify--alert'
    if (kind === 'news') return 'dashboard-notify--news'
    return 'dashboard-notify--system'
  }

  function renderDashboard(data) {
    var coursesEl = document.getElementById('active-courses-list')
    var newsEl = document.getElementById('system-notifications-list')
    var statsEl = document.getElementById('course-stats-list')
    var countEl = document.getElementById('active-courses-count')

    if (countEl) {
      var total = (data.active_courses || []).length
      countEl.textContent = total ? '(' + total + ')' : ''
    }

    applyMenuBadges(data.overview)

    renderList(coursesEl, data.active_courses, function (course) {
      var metaParts = []
      if (course.category_title) metaParts.push(escapeHtml(course.category_title))
      if (course.students_label) metaParts.push(escapeHtml(course.students_label))
      else if (course.students_count != null) metaParts.push(escapeHtml(studentsLabel(course.students_count)))
      var meta = metaParts.length ? '<span class="dashboard-course-meta">' + metaParts.join(' · ') + '</span>' : ''
      return (
        '<li><a class="dashboard-course-link" href="' +
        escapeHtml(course.href) +
        '"><span class="dashboard-course-title">' +
        escapeHtml(course.title) +
        '</span>' +
        meta +
        '</a></li>'
      )
    })

    renderList(newsEl, data.notifications, function (item) {
      var href = item.href && item.href !== '#' ? item.href : '/main'
      var timeHtml = item.time ? '<time class="dashboard-notify__time">' + escapeHtml(item.time) + '</time>' : ''
      return (
        '<li class="dashboard-notify ' +
        notifyClass(item.kind) +
        '"><a href="' +
        escapeHtml(href) +
        '"><span class="dashboard-notify__label">' +
        escapeHtml(item.label || 'Событие') +
        '</span><span class="dashboard-notify__title">' +
        escapeHtml(item.title) +
        '</span><span class="dashboard-notify__subtitle">' +
        escapeHtml(item.subtitle || '') +
        '</span>' +
        timeHtml +
        '</a></li>'
      )
    })

    renderList(statsEl, data.course_stats, function (course) {
      var label = studentsLabel(course.students_count)
      var completed =
        course.completed_count != null && course.completed_count > 0
          ? 'Завершили: ' + course.completed_count
          : 'Нет завершивших'
      return (
        '<li><a class="dashboard-course-link" href="' +
        escapeHtml(course.href) +
        '"><span class="dashboard-course-title">' +
        escapeHtml(course.title) +
        ' — ' +
        escapeHtml(label) +
        '</span><span class="dashboard-course-meta">' +
        escapeHtml(completed) +
        '</span></a></li>'
      )
    })
  }

  async function loadAdminDashboard() {
    var coursesEl = document.getElementById('active-courses-list')
    var newsEl = document.getElementById('system-notifications-list')
    var statsEl = document.getElementById('course-stats-list')
    if (!coursesEl && !newsEl && !statsEl) return

    try {
      var resp = await fetch('/api/admin/dashboard', { credentials: 'include' })
      var data
      if (resp.ok) {
        data = await resp.json()
      } else if (resp.status === 404) {
        console.warn('Эндпоинт /api/admin/dashboard не найден — fallback на /api/statistics и /api/courses')
        data = await loadAdminDashboardFallback()
      } else {
        var errBody = await resp.json().catch(function () { return {} })
        throw new Error((errBody && errBody.error) || 'HTTP ' + resp.status)
      }
      renderDashboard(data)
    } catch (e) {
      console.error('Не удалось загрузить данные дашборда', e)
      try {
        renderDashboard(await loadAdminDashboardFallback())
      } catch (e2) {
        console.error('Fallback дашборда тоже не сработал', e2)
        ;[coursesEl, newsEl, statsEl].forEach(function (el) {
          if (el) el.innerHTML = '<li class="dashboard-empty">Не удалось загрузить данные</li>'
        })
      }
    }
  }

  function escapeHtml(text) {
    if (text == null) return ''
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
  }

  async function init() {
    const user = await fetchCurrentUser()
    initChangeContentRootButton(user)
    loadAdminDashboard()
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()

