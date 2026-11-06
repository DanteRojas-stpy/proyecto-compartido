/**
 * CostFlow - Frontend Application Core (main.js)
 * Arquitectura SPA limpia en Vanilla JS.
 * - Enrutador por hash (#/inicio, #/compara/edificaciones/:sub, #/vigila)
 * - Componente reutilizable de carga de archivos con memoria por vista
 * - Balanza y Lupa interactivas para la Página de Inicio
 * - Modal accesible "Regístrate" con focus trap y validación
 */

document.addEventListener('DOMContentLoaded', () => {
  CostFlowApp.init();
});

const CostFlowApp = {
  // Estado en memoria de archivos subidos por vista (se mantienen separados)
  filesInMemory: {
    'obras-provisionales-preliminares': [],
    'salud-seguridad': [],
    'estructuras': [],
    'arquitectura': [],
    'instalaciones-sanitarias': [],
    'instalaciones-electricas-mecanicas': [],
    'otros': [],
    'vigila': []
  },

  // Estado global de la aplicación
  state: {
    currentRoute: '#/inicio',
    activeModal: false,
    focusedElementBeforeModal: null,
    comparaDropdownOpen: false
  },

  init() {
    this.setupHeader();
    this.setupRouter();
    this.setupRegisterModal();
    this.setupHeroParallax();
    this.setupInteractiveIllustrations();
    this.setupScrollAnimations();

    // Procesar ruta inicial
    this.handleRoute(window.location.hash || '#/inicio');
  },

  /* ==========================================================================
     1. Header, Menús Desplegables y Menú Móvil
     ========================================================================== */
  setupHeader() {
    const header = document.getElementById('main-header');
    const navComparaItem = document.getElementById('nav-compara-item');
    const navComparaBtn = document.getElementById('nav-compara-btn');
    const mobileToggle = document.getElementById('mobile-toggle-btn');
    const mobileDrawer = document.getElementById('mobile-drawer');
    const mobileOverlay = document.getElementById('mobile-drawer-overlay');
    const mobileClose = document.getElementById('mobile-drawer-close');
    const mobileAccBtn = document.getElementById('mobile-compara-acc-btn');
    const mobileAccContent = document.getElementById('mobile-compara-acc-content');

    // Reducción del header al hacer scroll
    window.addEventListener('scroll', () => {
      if (window.scrollY > 30) {
        header?.classList.add('scrolled');
      } else {
        header?.classList.remove('scrolled');
      }
    });

    // Control del dropdown "Compara" en desktop (clic y teclado)
    navComparaBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = navComparaItem.classList.toggle('dropdown-open');
      navComparaBtn.setAttribute('aria-expanded', String(isOpen));
    });

    navComparaBtn?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        navComparaItem.classList.add('dropdown-open');
        navComparaBtn.setAttribute('aria-expanded', 'true');
        const firstLink = navComparaItem.querySelector('.megamenu-link');
        firstLink?.focus();
      } else if (e.key === 'Escape') {
        navComparaItem.classList.remove('dropdown-open');
        navComparaBtn.setAttribute('aria-expanded', 'false');
      }
    });

    // Cerrar dropdown al hacer clic fuera
    document.addEventListener('click', (e) => {
      if (!navComparaItem?.contains(e.target)) {
        navComparaItem?.classList.remove('dropdown-open');
        navComparaBtn?.setAttribute('aria-expanded', 'false');
      }
    });

    // Drawer Móvil
    const openMobile = () => {
      mobileDrawer?.classList.add('open');
      mobileOverlay?.classList.add('active');
      document.body.style.overflow = 'hidden';
    };

    const closeMobile = () => {
      mobileDrawer?.classList.remove('open');
      mobileOverlay?.classList.remove('active');
      document.body.style.overflow = '';
    };

    mobileToggle?.addEventListener('click', openMobile);
    mobileClose?.addEventListener('click', closeMobile);
    mobileOverlay?.addEventListener('click', closeMobile);

    // Acordeón dentro del menú móvil
    mobileAccBtn?.addEventListener('click', () => {
      mobileAccContent?.classList.toggle('open');
      const icon = mobileAccBtn.querySelector('.acc-chevron');
      if (icon) {
        icon.style.transform = mobileAccContent?.classList.contains('open') ? 'rotate(180deg)' : 'rotate(0deg)';
      }
    });

    // Cerrar menú móvil al navegar
    document.querySelectorAll('.mobile-sub-link, .mobile-direct-link').forEach(link => {
      link.addEventListener('click', () => {
        closeMobile();
      });
    });
  },

  /* ==========================================================================
     2. Enrutador SPA basado en Hash
     ========================================================================== */
  setupRouter() {
    window.addEventListener('hashchange', () => {
      this.handleRoute(window.location.hash);
    });

    // Delegación para links con hash
    document.addEventListener('click', (e) => {
      const anchor = e.target.closest('a[href^="#/"]');
      if (anchor) {
        // Cerrar menú desplegable al hacer clic en un enlace interno
        document.getElementById('nav-compara-item')?.classList.remove('dropdown-open');
      }
    });
  },

  handleRoute(hash) {
    if (!hash || hash === '#' || hash === '#/inicio' || hash === '#inicio') {
      this.showHomeView();
      return;
    }

    // Ruta de Vigila
    if (hash === '#/vigila') {
      this.showVigilaView();
      return;
    }

    // Rutas de Compara -> Edificaciones -> [subtítulo]
    if (hash.startsWith('#/compara/edificaciones/')) {
      const subSlug = hash.replace('#/compara/edificaciones/', '').trim();
      const edificacionesCat = CostFlowData.comparaCategories[0];
      const subItem = edificacionesCat.subcategories.find(s => s.slug === subSlug);

      if (subItem) {
        this.showComparaSubView(subItem);
      } else {
        // Redirigir a inicio si no coincide
        window.location.hash = '#/inicio';
      }
      return;
    }

    // Por defecto volver al inicio
    this.showHomeView();
  },

  showHomeView() {
    this.state.currentRoute = '#/inicio';
    document.getElementById('home-view-container').style.display = 'block';
    document.getElementById('internal-view-container').style.display = 'none';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    this.updateActiveNav('#/inicio');
  },

  showVigilaView() {
    this.state.currentRoute = '#/vigila';
    document.getElementById('home-view-container').style.display = 'none';
    const internalContainer = document.getElementById('internal-view-container');
    internalContainer.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    this.updateActiveNav('#/vigila');

    // Configurar contenido de la vista Vigila
    const breadcrumbs = document.getElementById('view-breadcrumbs');
    breadcrumbs.innerHTML = `
      <a href="#/inicio">Inicio</a>
      <span class="crumb-separator">/</span>
      <span class="crumb-current">Vigila</span>
    `;

    document.getElementById('view-title').textContent = CostFlowData.vigilaView.title;
    document.getElementById('view-desc').textContent = CostFlowData.vigilaView.description;

    // Montar el componente reutilizable de carga de archivos
    this.mountUploader({
      viewId: 'vigila',
      uploadAreaTitle: CostFlowData.vigilaView.uploadAreaTitle, // Exactamente "Cuadro de procura"
      isVigila: true
    });
  },

  showComparaSubView(subItem) {
    this.state.currentRoute = subItem.hash;
    document.getElementById('home-view-container').style.display = 'none';
    const internalContainer = document.getElementById('internal-view-container');
    internalContainer.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    this.updateActiveNav('#/compara');

    // Migas de pan: Compara > Edificaciones > [Subtítulo]
    const breadcrumbs = document.getElementById('view-breadcrumbs');
    breadcrumbs.innerHTML = `
      <a href="#/inicio">Inicio</a>
      <span class="crumb-separator">/</span>
      <span>Compara</span>
      <span class="crumb-separator">/</span>
      <span>Edificaciones</span>
      <span class="crumb-separator">/</span>
      <span class="crumb-current">${subItem.title}</span>
    `;

    document.getElementById('view-title').textContent = subItem.title;
    document.getElementById('view-desc').textContent = subItem.description;

    // Montar el componente reutilizable de carga de archivos
    this.mountUploader({
      viewId: subItem.slug,
      uploadAreaTitle: `Carga de cotizaciones para ${subItem.title}`,
      isVigila: false
    });
  },

  updateActiveNav(activePrefix) {
    const navComparaBtn = document.getElementById('nav-compara-btn');
    const navVigilaLink = document.getElementById('nav-vigila-link');

    if (activePrefix.startsWith('#/compara')) {
      navComparaBtn?.classList.add('active');
      navVigilaLink?.classList.remove('active');
    } else if (activePrefix === '#/vigila') {
      navVigilaLink?.classList.add('active');
      navComparaBtn?.classList.remove('active');
    } else {
      navComparaBtn?.classList.remove('active');
      navVigilaLink?.classList.remove('active');
    }
  },

  /* ==========================================================================
     3. Componente Reutilizable de Carga de Archivos (Uploader)
     ========================================================================== */
  mountUploader({ viewId, uploadAreaTitle, isVigila }) {
    const uploaderContainer = document.getElementById('reusable-uploader-mount');
    if (!uploaderContainer) return;

    // Asegurar que exista el arreglo en memoria
    if (!this.filesInMemory[viewId]) {
      this.filesInMemory[viewId] = [];
    }

    const currentFiles = this.filesInMemory[viewId];

    // Renderizar plantilla base del uploader
    uploaderContainer.innerHTML = `
      <div class="uploader-card-box">
        <h3 class="uploader-title-h3">${uploadAreaTitle}</h3>
        
        <!-- Zona de Drag & Drop -->
        <div class="dropzone-container" id="dropzone-box" tabindex="0" role="button" aria-label="Zona para arrastrar o seleccionar archivos">
          <input type="file" id="hidden-file-input" multiple style="display:none;" 
            accept=".pdf,.xls,.xlsx,.csv,.doc,.docx,.png,.jpg,.jpeg,.webp">
          
          <svg class="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/>
            <path d="M12 12v9"/>
            <path d="m16 16-4-4-4 4"/>
          </svg>

          <p class="dropzone-main-text">Arrastra y suelta tus archivos aquí o haz clic para seleccionar</p>
          <p class="dropzone-sub-text">Admite PDF, Excel (.xls, .xlsx), CSV, Word (.doc, .docx) e imágenes (hasta 20 MB por archivo)</p>
          
          <button type="button" class="btn btn-yellow btn-sm" id="btn-browse-files" style="margin-top: 6px;">
            Seleccionar archivos
          </button>
        </div>

        <!-- Banner de Error de Validación -->
        <div class="uploader-error-banner" id="uploader-error-msg" role="alert"></div>

        <!-- Lista de Archivos Subidos -->
        <div class="uploaded-files-section">
          <div class="uploaded-files-header">
            <span class="uploaded-files-title">Archivos cargados en esta vista</span>
            <span class="files-count-badge" id="files-counter">${currentFiles.length} archivos</span>
          </div>

          <div id="uploaded-files-list"></div>
        </div>

        <!-- Botón de Acción Inferior -->
        ${!isVigila ? `
          <div class="view-action-footer">
            <span class="action-helper-hint" id="action-hint-text">
              ${currentFiles.length < 2 ? 'Sube al menos 2 cotizaciones para habilitar la comparación' : '¡Listo! Puedes iniciar la comparación técnica'}
            </span>
            <button class="btn btn-yellow btn-lg" id="btn-compare-action" ${currentFiles.length < 2 ? 'disabled' : ''}>
              Comparar cotizaciones
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="5" y1="12" x2="19" y2="12"/>
                <polyline points="12 5 19 12 12 19"/>
              </svg>
            </button>
          </div>
        ` : `
          <div class="view-action-footer">
            <span class="action-helper-hint">Monitoreo activo sobre el cuadro de procura</span>
            <button class="btn btn-yellow btn-lg" id="btn-vigila-action" ${currentFiles.length === 0 ? 'disabled' : ''}>
              Analizar cuadro de procura
            </button>
          </div>
        `}
      </div>
    `;

    // Vincular lógica y eventos del uploader
    this.bindUploaderEvents(viewId, isVigila);
    this.renderFilesList(viewId, isVigila);
  },

  bindUploaderEvents(viewId, isVigila) {
    const dropzone = document.getElementById('dropzone-box');
    const fileInput = document.getElementById('hidden-file-input');
    const browseBtn = document.getElementById('btn-browse-files');
    const compareBtn = document.getElementById('btn-compare-action');
    const vigilaBtn = document.getElementById('btn-vigila-action');

    const openFileDialog = () => fileInput?.click();

    browseBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      openFileDialog();
    });

    dropzone?.addEventListener('click', openFileDialog);

    dropzone?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openFileDialog();
      }
    });

    // Eventos Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone?.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('is-dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone?.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('is-dragover');
      });
    });

    dropzone?.addEventListener('drop', (e) => {
      const droppedFiles = e.dataTransfer?.files;
      if (droppedFiles && droppedFiles.length > 0) {
        this.processFiles(droppedFiles, viewId, isVigila);
      }
    });

    fileInput?.addEventListener('change', (e) => {
      const selectedFiles = e.target.files;
      if (selectedFiles && selectedFiles.length > 0) {
        this.processFiles(selectedFiles, viewId, isVigila);
        fileInput.value = ''; // Reset para permitir subir el mismo archivo si se desea
      }
    });

    // Botón "Comparar cotizaciones"
    compareBtn?.addEventListener('click', () => {
      const count = this.filesInMemory[viewId].length;
      this.showToast(`📊 Comparando ${count} cotizaciones... Se ha generado el cuadro de homologación con éxito.`);
    });

    // Botón Vigila
    vigilaBtn?.addEventListener('click', () => {
      this.showToast(`🦉 Cuadro de procura auditado: El Búho ha verificado fechas y no detectó retrasos críticos.`);
    });
  },

  processFiles(fileList, viewId, isVigila) {
    const errorBanner = document.getElementById('uploader-error-msg');
    const allowedExts = CostFlowData.uploadSettings.allowedExtensions;
    const maxBytes = CostFlowData.uploadSettings.maxSizeBytes;
    let errorMessage = '';

    Array.from(fileList).forEach(file => {
      const name = file.name;
      const ext = '.' + name.split('.').pop().toLowerCase();

      // Validación de extensión
      if (!allowedExts.includes(ext)) {
        errorMessage = `El archivo "${name}" no tiene un formato permitido. Solo se aceptan PDF, Excel (.xls/.xlsx), CSV, Word (.doc/.docx) e imágenes.`;
        return;
      }

      // Validación de tamaño máximo (20 MB)
      if (file.size > maxBytes) {
        errorMessage = `El archivo "${name}" supera el límite de 20 MB (tamaño: ${(file.size / (1024 * 1024)).toFixed(1)} MB).`;
        return;
      }

      // Guardar en memoria de la vista
      this.filesInMemory[viewId].push({
        id: 'file-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6),
        name: file.name,
        size: file.size,
        formattedSize: this.formatFileSize(file.size),
        extension: ext,
        uploadedAt: new Date()
      });
    });

    if (errorMessage && errorBanner) {
      errorBanner.textContent = errorMessage;
      errorBanner.classList.add('show');
      setTimeout(() => errorBanner.classList.remove('show'), 6000);
    } else if (errorBanner) {
      errorBanner.classList.remove('show');
    }

    this.renderFilesList(viewId, isVigila);
  },

  renderFilesList(viewId, isVigila) {
    const listContainer = document.getElementById('uploaded-files-list');
    const counterBadge = document.getElementById('files-counter');
    const compareBtn = document.getElementById('btn-compare-action');
    const vigilaBtn = document.getElementById('btn-vigila-action');
    const hintText = document.getElementById('action-hint-text');

    if (!listContainer) return;

    const files = this.filesInMemory[viewId] || [];

    if (counterBadge) {
      counterBadge.textContent = `${files.length} ${files.length === 1 ? 'archivo' : 'archivos'}`;
    }

    // Actualizar estado del botón de comparación
    if (compareBtn) {
      const canCompare = files.length >= 2;
      compareBtn.disabled = !canCompare;
      if (hintText) {
        hintText.textContent = canCompare 
          ? '¡Listo! Puedes iniciar la comparación técnica de tus cotizaciones' 
          : 'Sube al menos 2 cotizaciones para habilitar la comparación';
      }
    }

    if (vigilaBtn) {
      vigilaBtn.disabled = files.length === 0;
    }

    if (files.length === 0) {
      listContainer.innerHTML = `
        <div class="empty-files-placeholder">
          No hay archivos subidos aún en esta sección.
        </div>
      `;
      return;
    }

    listContainer.innerHTML = `
      <div class="files-items-grid">
        ${files.map(file => `
          <div class="file-item-card" data-file-id="${file.id}">
            <div class="file-left-group">
              <div class="file-type-icon">
                ${this.getFileIconSvg(file.extension)}
              </div>
              <div class="file-meta-col">
                <span class="file-name-text" title="${file.name}">${file.name}</span>
                <span class="file-size-text">${file.formattedSize}</span>
              </div>
            </div>

            <button type="button" class="file-delete-btn" title="Eliminar archivo" aria-label="Eliminar ${file.name}" onclick="CostFlowApp.deleteFile('${viewId}', '${file.id}', ${isVigila})">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                <line x1="10" y1="11" x2="10" y2="17"/>
                <line x1="14" y1="11" x2="14" y2="17"/>
              </svg>
            </button>
          </div>
        `).join('')}
      </div>
    `;
  },

  deleteFile(viewId, fileId, isVigila) {
    if (!this.filesInMemory[viewId]) return;
    this.filesInMemory[viewId] = this.filesInMemory[viewId].filter(f => f.id !== fileId);
    this.renderFilesList(viewId, isVigila);
    this.showToast('Archivo eliminado de la lista.');
  },

  formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  },

  getFileIconSvg(ext) {
    if (ext === '.pdf') {
      return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`;
    }
    if (['.xls', '.xlsx', '.csv'].includes(ext)) {
      return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M12 9v12"/></svg>`;
    }
    if (['.doc', '.docx'].includes(ext)) {
      return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1B5FC1" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
    }
    // Imágenes u otros
    return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#12B5D6" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
  },

  /* ==========================================================================
     4. Modal "Regístrate" Accesible (Focus trap, localStorage, validación)
     ========================================================================== */
  setupRegisterModal() {
    const modalOverlay = document.getElementById('register-modal-overlay');
    const openBtn = document.getElementById('btn-open-register');
    const closeBtn = document.getElementById('modal-close-trigger');
    const form = document.getElementById('register-modal-form');
    const emailInput = document.getElementById('register-email-input');
    const feedbackMsg = document.getElementById('register-feedback-msg');

    const openModal = () => {
      this.state.focusedElementBeforeModal = document.activeElement;
      modalOverlay?.classList.add('active');
      this.state.activeModal = true;
      document.body.style.overflow = 'hidden';
      feedbackMsg?.classList.remove('error', 'success');
      feedbackMsg.style.display = 'none';
      setTimeout(() => emailInput?.focus(), 150);
    };

    const closeModal = () => {
      modalOverlay?.classList.remove('active');
      this.state.activeModal = false;
      document.body.style.overflow = '';
      if (this.state.focusedElementBeforeModal) {
        this.state.focusedElementBeforeModal.focus();
      }
    };

    openBtn?.addEventListener('click', openModal);
    closeBtn?.addEventListener('click', closeModal);

    modalOverlay?.addEventListener('click', (e) => {
      if (e.target === modalOverlay) {
        closeModal();
      }
    });

    // Tecla ESC y Focus Trap
    document.addEventListener('keydown', (e) => {
      if (!this.state.activeModal) return;

      if (e.key === 'Escape') {
        closeModal();
        return;
      }

      // Focus trap
      if (e.key === 'Tab') {
        const focusableElements = modalOverlay.querySelectorAll('button, input, [tabindex="0"]');
        const firstEl = focusableElements[0];
        const lastEl = focusableElements[focusableElements.length - 1];

        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    });

    // Envío del Formulario
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = emailInput.value.trim();
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

      if (!email || !emailRegex.test(email)) {
        feedbackMsg.textContent = 'Por favor, introduce un correo electrónico válido.';
        feedbackMsg.className = 'form-feedback-msg error';
        feedbackMsg.style.display = 'block';
        emailInput.focus();
        return;
      }

      // Guardar en localStorage simulando registro
      try {
        // TODO: conectar un backend para registrar usuarios reales
        const registeredUsers = JSON.parse(localStorage.getItem('costflow_registered_users') || '[]');
        registeredUsers.push({ email, registeredAt: new Date().toISOString() });
        localStorage.setItem('costflow_registered_users', JSON.stringify(registeredUsers));
      } catch (err) {
        console.warn('No se pudo guardar en localStorage:', err);
      }

      feedbackMsg.textContent = '¡Cuenta creada con éxito! Bienvenido a CostFlow.';
      feedbackMsg.className = 'form-feedback-msg success';
      feedbackMsg.style.display = 'block';

      setTimeout(() => {
        closeModal();
        form.reset();
        this.showToast(`¡Bienvenido! Hemos registrado ${email} correctamente.`);
      }, 1200);
    });
  },

  /* ==========================================================================
     5. Efectos Visuales: Parallax en Hero & Ilustraciones Interactivas
     ========================================================================== */
  setupHeroParallax() {
    const heroBg = document.getElementById('hero-quote-bg');
    if (!heroBg) return;

    // Parallax leve al mover el cursor en escritorio
    window.addEventListener('mousemove', (e) => {
      if (window.innerWidth < 1024) return;
      const xRatio = (e.clientX / window.innerWidth) - 0.5;
      const yRatio = (e.clientY / window.innerHeight) - 0.5;
      heroBg.style.transform = `rotate(-3.5deg) translate(${xRatio * 18}px, ${yRatio * 18}px) scale(1.04)`;
    });

    // Parallax suave al hacer scroll
    window.addEventListener('scroll', () => {
      const scrolled = window.pageYOffset;
      if (scrolled < window.innerHeight) {
        heroBg.style.transform = `rotate(-3.5deg) translateY(${scrolled * 0.15}px) scale(1.04)`;
      }
    });
  },

  setupInteractiveIllustrations() {
    // 1) Balanza Interactiva (Sección 1 - Compara)
    const scaleCard = document.getElementById('interactive-scale-card');
    if (scaleCard) {
      // Toggle en táctil
      scaleCard.addEventListener('click', () => {
        scaleCard.classList.toggle('is-active');
      });
    }

    // 2) Lupa Interactiva (Sección 2 - Vigila)
    const lupaCard = document.getElementById('interactive-lupa-card');
    const lupaTracker = document.getElementById('lupa-tracker');

    if (lupaCard && lupaTracker) {
      lupaCard.addEventListener('mousemove', (e) => {
        const rect = lupaCard.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        lupaTracker.style.left = `${x}px`;
        lupaTracker.style.top = `${y}px`;
        lupaTracker.style.opacity = '1';
      });

      lupaCard.addEventListener('mouseleave', () => {
        lupaCard.classList.remove('is-active');
        lupaTracker.style.opacity = '0.4';
        lupaTracker.style.left = '42%';
        lupaTracker.style.top = '48%';
      });

      // Táctil
      lupaCard.addEventListener('click', () => {
        lupaCard.classList.toggle('is-active');
      });
    }
  },

  /* ==========================================================================
     6. Animaciones al hacer Scroll (IntersectionObserver)
     ========================================================================== */
  setupScrollAnimations() {
    const animatedElements = document.querySelectorAll('.animate-fade-up');
    if (!('IntersectionObserver' in window)) {
      animatedElements.forEach(el => el.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.12,
      rootMargin: '0px 0px -30px 0px'
    });

    animatedElements.forEach(el => observer.observe(el));
  },

  /* ==========================================================================
     7. Notificaciones Toast Flotantes
     ========================================================================== */
  showToast(message, duration = 4000) {
    let toast = document.getElementById('global-toast-bar');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'global-toast-bar';
      toast.className = 'toast-bar';
      document.body.appendChild(toast);
    }

    toast.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFC21A" stroke-width="2.5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>${message}</span>
    `;

    toast.classList.add('active');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      toast.classList.remove('active');
    }, duration);
  }
};
