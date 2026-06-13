"""Design system -- Daangn Ad Reporter brand theme.

Provides inject_theme() which adds the full CSS design system to the current page.
Call once per page (idempotent via JS guard).
"""
from nicegui import ui

BRAND_CSS = """
/* == Paperlogy Font Family == */
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-1Thin.ttf') format('truetype'); font-weight: 100; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-2ExtraLight.ttf') format('truetype'); font-weight: 200; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-3Light.ttf') format('truetype'); font-weight: 300; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-4Regular.ttf') format('truetype'); font-weight: 400; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-5Medium.ttf') format('truetype'); font-weight: 500; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-6SemiBold.ttf') format('truetype'); font-weight: 600; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-7Bold.ttf') format('truetype'); font-weight: 700; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-8ExtraBold.ttf') format('truetype'); font-weight: 800; font-style: normal; font-display: swap; }
@font-face { font-family: 'Paperlogy'; src: url('/static/fonts/Paperlogy-9Black.ttf') format('truetype'); font-weight: 900; font-style: normal; font-display: swap; }

:root {
    --dg-primary: #FF6F0F;
    --dg-primary-hover: #E55A00;
    --dg-primary-light: #FFF1E5;
    --dg-primary-50: #FFF8F2;
    /* 차분한 뉴트럴 (management 팔레트 기반) — 오렌지는 포인트로만 */
    --dg-surface: #F8F9FC;
    --dg-card: #FFFFFF;
    --dg-text-primary: #1A1A2E;
    --dg-text-secondary: #4B5563;
    --dg-text-tertiary: #6B7280;
    --dg-text-caption: #9CA3AF;
    --dg-border: #E6E7EA;
    --dg-border-light: #F0F1F3;
    --dg-success: #16A34A;
    --dg-success-light: #ECFDF3;
    --dg-warning: #D97706;
    --dg-warning-light: #FFF7E8;
    --dg-error: #DC2626;
    --dg-error-light: #FDECEC;
    --dg-info: #2563EB;
    --dg-info-light: #EFF4FC;
    --dg-radius: 16px;
    --dg-radius-sm: 10px;
    --dg-radius-xs: 6px;
    --dg-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.04);
    --dg-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
    --dg-shadow-lg: 0 8px 24px rgba(15, 23, 42, 0.08);
    --dg-sidebar-width: 240px;
    --dg-sidebar-bg: #F1F3F7;
    --dg-header-height: 56px;
}

/* == Global == */
body, .q-page {
    font-family: 'Paperlogy', -apple-system,
                 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif !important;
    background: var(--dg-surface) !important;
    color: var(--dg-text-primary);
    -webkit-font-smoothing: antialiased;
}

/* == Header == */
.dg-header {
    background: var(--dg-card) !important;
    border-bottom: 1px solid var(--dg-border) !important;
    box-shadow: none !important;
    height: var(--dg-header-height) !important;
    color: var(--dg-text-primary) !important;
}
.dg-logo {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: var(--dg-primary) !important;
    letter-spacing: -0.3px;
}
.dg-header-version {
    font-size: 11px !important;
    color: var(--dg-text-caption) !important;
    background: var(--dg-surface);
    padding: 2px 8px;
    border-radius: 10px;
}

/* == Sidebar (management 스타일: 틴트 배경 + 필 활성) == */
.dg-sidebar {
    background: var(--dg-sidebar-bg) !important;
    border-right: 1px solid var(--dg-border) !important;
    padding-top: 0 !important;
    width: var(--dg-sidebar-width) !important;
    min-width: var(--dg-sidebar-width) !important;
}
.dg-workspace-header {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--dg-border);
}
.dg-sidebar .q-drawer__content { overflow-x: hidden; overflow-y: auto; }
.dg-nav-section-label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: var(--dg-text-caption) !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 16px 16px 6px;
}
.dg-nav-item {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 10px 14px !important;
    margin: 2px 8px !important;
    border-radius: var(--dg-radius-sm) !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--dg-text-secondary) !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    background: transparent !important;
    width: calc(100% - 16px) !important;
    text-align: left !important;
    min-height: 42px !important;
    text-transform: none !important;
    letter-spacing: -0.1px !important;
    border: none !important;
    white-space: nowrap !important;
    overflow: hidden !important;
}
.dg-nav-item .q-btn__content {
    flex-wrap: nowrap !important;
    justify-content: flex-start !important;
}
.dg-nav-item:hover {
    background: var(--dg-card) !important;
    color: var(--dg-text-primary) !important;
}
.dg-nav-item.active {
    background: var(--dg-primary) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 4px rgba(15,23,42,0.12) !important;
}
.dg-nav-item.active:hover {
    background: var(--dg-primary-hover) !important;
    color: #FFFFFF !important;
}
.dg-nav-item.active .q-icon {
    color: #FFFFFF !important;
}
.dg-nav-item .q-icon {
    font-size: 20px !important;
    color: var(--dg-text-tertiary) !important;
}
.dg-nav-item.active .q-btn__content { color: #FFFFFF !important; }

/* == Cards == */
.dg-card {
    background: var(--dg-card) !important;
    border-radius: var(--dg-radius) !important;
    box-shadow: var(--dg-shadow-sm) !important;
    border: 1px solid var(--dg-border-light) !important;
    padding: 24px !important;
    transition: box-shadow 0.2s ease !important;
}
.dg-card:hover { box-shadow: var(--dg-shadow) !important; }
.dg-card-flat {
    background: var(--dg-card) !important;
    border-radius: var(--dg-radius) !important;
    box-shadow: none !important;
    border: 1px solid var(--dg-border) !important;
    padding: 24px !important;
}
.dg-card-accent {
    background: var(--dg-primary-50) !important;
    border-radius: var(--dg-radius) !important;
    box-shadow: none !important;
    border: 1px solid #FFE0C2 !important;
    padding: 20px !important;
}

/* == Section Headers == */
.dg-section-icon {
    font-size: 20px !important;
    color: var(--dg-primary) !important;
    background: var(--dg-primary-light);
    width: 36px; height: 36px;
    display: flex; align-items: center; justify-content: center;
    border-radius: var(--dg-radius-xs);
    flex-shrink: 0;
}
.dg-section-title {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: var(--dg-text-primary) !important;
    letter-spacing: -0.2px;
}
.dg-section-subtitle {
    font-size: 13px !important;
    color: var(--dg-text-tertiary) !important;
    font-weight: 400 !important;
}

/* == Buttons == */
.dg-btn-primary {
    background: var(--dg-primary) !important;
    color: white !important;
    border-radius: var(--dg-radius-sm) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 24px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
    min-height: 40px !important;
}
.dg-btn-primary:hover {
    background: var(--dg-primary-hover) !important;
    box-shadow: 0 2px 8px rgba(15,23,42,0.12) !important;
    transform: translateY(-1px);
}
.dg-btn-secondary {
    background: var(--dg-card) !important;
    color: var(--dg-text-secondary) !important;
    border: 1px solid var(--dg-border) !important;
    border-radius: var(--dg-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    min-height: 40px !important;
}
.dg-btn-secondary:hover {
    background: var(--dg-surface) !important;
    border-color: var(--dg-text-caption) !important;
    transform: translateY(-1px);
}
.dg-btn-success:hover {
    box-shadow: 0 2px 8px rgba(15,23,42,0.12) !important;
    transform: translateY(-1px);
}
.dg-btn-success {
    background: var(--dg-success) !important;
    color: white !important;
    border-radius: var(--dg-radius-sm) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 24px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    min-height: 40px !important;
}
.dg-btn-danger {
    background: transparent !important;
    color: var(--dg-error) !important;
    border: 1px solid var(--dg-error) !important;
    border-radius: var(--dg-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    min-height: 40px !important;
}
.dg-btn-ghost {
    background: transparent !important;
    color: var(--dg-primary) !important;
    border-radius: var(--dg-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 8px 16px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    min-height: 36px !important;
}
.dg-btn-ghost:hover { background: var(--dg-primary-light) !important; }
.dg-btn-sm {
    font-size: 13px !important;
    padding: 4px 14px !important;
    min-height: 32px !important;
}

/* == KPI == */
.dg-kpi-grid {
    display: grid !important;
    grid-template-columns: repeat(auto-fill, minmax(155px, 1fr)) !important;
    gap: 12px !important;
    width: 100% !important;
    min-width: 0 !important;
}
.dg-kpi-card {
    background: var(--dg-card) !important;
    border: 1px solid var(--dg-border-light) !important;
    border-radius: var(--dg-radius-sm) !important;
    padding: 16px !important;
    text-align: center !important;
    transition: all 0.15s ease !important;
    min-width: 0 !important;
}

/* == Dashboard stat cards (Meta-style summary row) == */
.dg-stat-card {
    background: var(--dg-card);
    border: 1px solid var(--dg-border);
    border-radius: var(--dg-radius-sm);
    padding: 18px 20px 14px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dg-stat-card:hover {
    border-color: #D5DAE1;
    box-shadow: var(--dg-shadow);
    transform: translateY(-1px);
}
.dg-stat-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--dg-text-tertiary);
    letter-spacing: -0.1px;
}
.dg-stat-value {
    font-size: 24px;
    font-weight: 800;
    color: var(--dg-text-primary);
    letter-spacing: -0.6px;
    line-height: 1.2;
}
.dg-stat-sub {
    font-size: 11.5px;
    color: var(--dg-text-caption);
}
.dg-stat-delta {
    font-size: 11.5px;
    font-weight: 700;
    margin-top: 2px;
}
.dg-stat-delta-good { color: var(--dg-success); }
.dg-stat-delta-bad { color: var(--dg-error); }
.dg-stat-delta-neutral { color: var(--dg-text-tertiary); }
/* 히어로 카드 — 총 광고비 시각 앵커 (2칸 스팬, 차분한 강조) */
.dg-stat-card--hero {
    grid-column: span 2;
    background: var(--dg-card);
    border: 1px solid var(--dg-border);
    border-top: 3px solid var(--dg-primary);
}
.dg-stat-card--hero .dg-stat-value { font-size: 28px; }
.dg-kpi-card:hover {
    border-color: #D5DAE1 !important;
    box-shadow: var(--dg-shadow) !important;
}
.dg-kpi-label {
    font-size: 12px !important;
    color: var(--dg-text-tertiary) !important;
    font-weight: 500 !important;
    margin-bottom: 4px !important;
}
.dg-kpi-value {
    font-size: 20px !important;
    font-weight: 700 !important;
    color: var(--dg-text-primary) !important;
}
.dg-kpi-value-accent {
    font-size: 20px !important;
    font-weight: 700 !important;
    color: var(--dg-primary) !important;
}

/* == Form == */
.dg-input .q-field__control { border-radius: var(--dg-radius-sm) !important; }
.dg-input .q-field__label { font-weight: 500 !important; color: var(--dg-text-secondary) !important; }
.dg-select .q-field__control { border-radius: var(--dg-radius-sm) !important; }

/* == Tabs == */
.dg-tabs .q-tab {
    text-transform: none !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    letter-spacing: 0 !important;
    min-height: 44px !important;
    padding: 0 20px !important;
}
.dg-tabs .q-tab--active {
    color: var(--dg-primary) !important;
    font-weight: 600 !important;
}
.dg-tabs .q-tab__indicator {
    background: var(--dg-primary) !important;
    height: 3px !important;
    border-radius: 3px 3px 0 0 !important;
}

/* == Badges == */
.dg-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500;
}
.dg-badge-success { background: var(--dg-success-light); color: #2E7D32; }
.dg-badge-warning { background: var(--dg-warning-light); color: #E65100; }
.dg-badge-error   { background: var(--dg-error-light);   color: #C62828; }
.dg-badge-info    { background: var(--dg-info-light);    color: #1565C0; }

/* == Banners == */
.dg-banner {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 20px; border-radius: var(--dg-radius-sm);
    font-size: 13px; font-weight: 500;
}
.dg-banner-info    { background: var(--dg-surface); color: var(--dg-text-secondary); border: 1px solid var(--dg-border); }
.dg-banner-info .q-icon { color: var(--dg-text-tertiary); }
.dg-banner-success { background: var(--dg-success-light); color: #2E7D32; border: 1px solid #C8E6C9; }
.dg-banner-warning { background: var(--dg-warning-light); color: #E65100; border: 1px solid #FFE0B2; }
.dg-banner-error   { background: var(--dg-error-light);   color: #C62828; border: 1px solid #FFCDD2; }

/* == Tables == */
.dg-table .q-table__container {
    border-radius: var(--dg-radius-sm) !important;
    border: 1px solid var(--dg-border-light) !important;
    box-shadow: none !important;
}
.dg-table thead th {
    background: var(--dg-surface) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    color: var(--dg-text-secondary) !important;
}
.dg-table tbody td {
    font-size: 13px !important;
    color: var(--dg-text-primary) !important;
}
.dg-table tbody tr:nth-child(even) td { background: #FAFBFC !important; }
.dg-table tbody tr:hover td { background: var(--dg-surface) !important; }

/* == Upload == */
.dg-upload .q-uploader {
    border-radius: var(--dg-radius-sm) !important;
    border: 2px dashed var(--dg-border) !important;
    background: var(--dg-surface) !important;
}
.dg-upload .q-uploader__header,
.q-uploader__header {
    background: #4B5563 !important;
    border-radius: var(--dg-radius-sm) var(--dg-radius-sm) 0 0 !important;
}

/* == Expansion == */
.dg-expansion .q-expansion-item__container {
    border: 1px solid var(--dg-border-light) !important;
    border-radius: var(--dg-radius-sm) !important;
    overflow: hidden;
}
.dg-expansion .q-item { min-height: 48px !important; padding: 8px 16px !important; }
.dg-expansion .q-item:hover { background: var(--dg-surface) !important; }
.dg-expansion .q-item__label { font-weight: 600 !important; font-size: 14px !important; }

/* == Progress == */
.dg-progress-text {
    font-size: 13px !important;
    color: var(--dg-text-tertiary) !important;
    font-weight: 500 !important;
}

/* == Empty State == */
.dg-empty { text-align: center; padding: 48px 24px; }
.dg-empty-icon { font-size: 56px !important; color: var(--dg-border) !important; margin-bottom: 16px; }
.dg-empty-text { font-size: 15px !important; color: var(--dg-text-tertiary) !important; }

/* == Project Card Grid == */
.dg-project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
    width: 100%;
}
.dg-project-card {
    background: var(--dg-card);
    border: 1px solid var(--dg-border);
    border-radius: var(--dg-radius);
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    cursor: pointer;
    min-width: 0;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dg-project-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--dg-shadow-lg);
    border-color: #D5DAE1;
}
.dg-project-card.active {
    border-color: var(--dg-primary);
    background: var(--dg-card);
}
.dg-avatar {
    width: 40px; height: 40px;
    border-radius: 12px;
    background: var(--dg-primary-light);
    color: var(--dg-primary);
    font-weight: 800;
    font-size: 16px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.dg-project-card-title {
    font-size: 15px; font-weight: 700; letter-spacing: -0.3px;
    color: var(--dg-text-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dg-project-card-sub {
    font-size: 12px; color: var(--dg-text-tertiary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dg-quick-link {
    color: var(--dg-text-secondary) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-transform: none !important;
}
.dg-quick-link:hover { color: var(--dg-primary) !important; }
.dg-quick-link .q-icon { color: var(--dg-text-caption) !important; }
.dg-quick-link:hover .q-icon { color: var(--dg-primary) !important; }
.dg-meta-chip {
    font-size: 11.5px; font-weight: 500;
    padding: 3px 10px; border-radius: 999px;
    background: var(--dg-surface);
    color: var(--dg-text-secondary);
    border: 1px solid var(--dg-border-light);
    white-space: nowrap;
}

/* == Project List == */
.dg-project-item {
    display: flex !important; align-items: center !important; gap: 10px !important;
    padding: 10px 14px !important; margin: 3px 0 !important;
    border-radius: var(--dg-radius-sm) !important;
    cursor: pointer !important; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    background: var(--dg-surface) !important; border: 1px solid var(--dg-border-light) !important;
    width: 100% !important; text-align: left !important;
    min-height: 42px !important; font-size: 14px !important;
    font-weight: 500 !important; color: var(--dg-text-secondary) !important;
    text-transform: none !important; letter-spacing: -0.1px !important;
}
.dg-project-item .q-btn__content { flex-wrap: nowrap !important; justify-content: flex-start !important; gap: 10px !important; }
.dg-project-item .q-icon { font-size: 18px !important; color: var(--dg-text-caption) !important; flex-shrink: 0 !important; }
.dg-project-item:hover { background: var(--dg-card) !important; border-color: #D5DAE1 !important; box-shadow: var(--dg-shadow-sm) !important; }
.dg-project-item:hover .q-icon { color: var(--dg-primary) !important; }
.dg-project-item.active {
    background: var(--dg-primary-light) !important;
    color: var(--dg-primary) !important;
    font-weight: 600 !important;
    border-color: var(--dg-primary) !important;
    box-shadow: 0 0 0 1px var(--dg-primary), 0 2px 8px rgba(255,111,15,0.15) !important;
}
.dg-project-item.active .q-icon { color: var(--dg-primary) !important; }

/* == Scrollbar == */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--dg-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--dg-text-caption); }

/* == Page Content == */
.dg-page-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 32px;
}
.dg-page-title {
    font-size: 29px !important; font-weight: 800 !important;
    color: var(--dg-text-primary) !important; letter-spacing: -1px;
    margin-bottom: 6px !important; line-height: 1.15 !important;
}
.dg-page-subtitle {
    font-size: 14px !important;
    color: var(--dg-text-tertiary) !important;
    margin-bottom: 28px !important;
    line-height: 1.5 !important;
    letter-spacing: -0.1px !important;
}

/* == Image / Chart == */
.dg-image-preview {
    border-radius: var(--dg-radius-sm) !important;
    overflow: hidden; border: 1px solid var(--dg-border-light);
}
.dg-chart-img {
    border-radius: var(--dg-radius-sm) !important;
    border: 1px solid var(--dg-border-light) !important;
    max-width: 400px;
}

/* == History strip == */
.dg-history-item {
    border-radius: var(--dg-radius-xs) !important;
    border: 2px solid transparent !important;
    transition: all 0.15s ease !important; cursor: pointer;
}
.dg-history-item:hover { border-color: var(--dg-primary) !important; }

/* == Markdown Prose == */
.dg-prose { font-size: 14px !important; line-height: 1.8 !important; color: var(--dg-text-secondary) !important; letter-spacing: -0.1px !important; }
.dg-prose h2 {
    font-size: 18px !important; font-weight: 700 !important;
    color: var(--dg-text-primary) !important; margin-top: 28px !important; margin-bottom: 12px !important;
    letter-spacing: -0.3px !important;
}
.dg-prose h3 { font-size: 15px !important; font-weight: 600 !important; color: var(--dg-text-primary) !important; letter-spacing: -0.2px !important; margin-top: 20px !important; }
.dg-prose table { width: 100% !important; border-collapse: collapse !important; margin: 12px 0 !important; font-size: 13px !important; }
.dg-prose th { background: var(--dg-surface) !important; padding: 8px 12px !important; font-weight: 600 !important; text-align: left !important; border-bottom: 2px solid var(--dg-border) !important; }
.dg-prose td { padding: 8px 12px !important; border-bottom: 1px solid var(--dg-border-light) !important; }

/* == Radio == */
.dg-radio .q-radio__label { font-size: 14px !important; font-weight: 500 !important; }
.dg-radio .q-radio__inner--truthy .q-radio__bg { color: var(--dg-primary) !important; }

/* == Misc == */
.dg-divider { border-top: 1px solid var(--dg-border-light); margin: 16px 0; }
.dg-label-sm { font-size: 13px !important; font-weight: 500 !important; color: var(--dg-text-tertiary) !important; }
.dg-text-sm { font-size: 13px !important; color: var(--dg-text-secondary) !important; }
.dg-mono { font-family: 'SF Mono','Consolas','Monaco',monospace !important; font-size: 12px !important; }

/* == Tactile Feedback (taste-skill Rule 5) == */
.dg-btn-primary:active { transform: scale(0.98) translateY(1px) !important; }
.dg-btn-secondary:active { transform: scale(0.98) translateY(1px) !important; }
.dg-btn-success:active { transform: scale(0.98) translateY(1px) !important; }
.dg-btn-ghost:active { transform: scale(0.98) !important; }
.dg-nav-item:active { transform: scale(0.98) !important; }

/* == Enhanced Transitions (taste-skill Rule 4) == */
.dg-btn-primary, .dg-btn-secondary, .dg-btn-success, .dg-btn-danger, .dg-btn-ghost {
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.dg-card { transition: box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important; }

/* == Dialogs == */
.dg-dialog .q-card { border-radius: var(--dg-radius) !important; padding: 24px !important; }

/* == Validation Banner == */
.dg-validation-pass {
    background: var(--dg-success-light) !important;
    color: #2E7D32 !important;
    border: 1px solid #C8E6C9 !important;
    border-radius: var(--dg-radius-sm) !important;
    padding: 10px 16px !important;
    font-size: 13px !important; font-weight: 600 !important;
}
.dg-validation-fail {
    background: var(--dg-error-light) !important;
    color: #C62828 !important;
    border: 1px solid #FFCDD2 !important;
    border-radius: var(--dg-radius-sm) !important;
    padding: 10px 16px !important;
    font-size: 13px !important; font-weight: 600 !important;
}

/* == Wizard Step Indicator == */
.dg-wizard-steps { display: flex; align-items: center; gap: 0; padding: 20px 0; }
.dg-wizard-step { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; position: relative; cursor: pointer; }
.dg-wizard-step-circle { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
.dg-wizard-step.active .dg-wizard-step-circle { background: var(--dg-primary); color: white; }
.dg-wizard-step.completed .dg-wizard-step-circle { background: var(--dg-success); color: white; }
.dg-wizard-step.disabled .dg-wizard-step-circle { background: var(--dg-border-light); color: var(--dg-text-caption); }
.dg-wizard-step.pending .dg-wizard-step-circle { background: var(--dg-surface); color: var(--dg-text-tertiary); border: 2px solid var(--dg-border); }
.dg-wizard-step-label { font-size: 12px; font-weight: 500; color: var(--dg-text-tertiary); }
.dg-wizard-step.active .dg-wizard-step-label { color: var(--dg-primary); font-weight: 600; }
.dg-wizard-step.completed .dg-wizard-step-label { color: var(--dg-success); }
.dg-wizard-step-line { position: absolute; top: 18px; left: 50%; width: 100%; height: 2px; background: var(--dg-border-light); z-index: -1; }
.dg-wizard-step.completed .dg-wizard-step-line { background: var(--dg-success); }
/* Wizard Content Containers */
.dg-wizard-content { min-height: 400px; }
.dg-wizard-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 60px 24px; text-align: center; }
.dg-wizard-placeholder-icon { font-size: 48px; color: var(--dg-border); }
.dg-wizard-placeholder-text { font-size: 15px; color: var(--dg-text-tertiary); }

/* == Funnel Visualization == */
.dg-funnel { display: flex; align-items: stretch; gap: 2px; width: 100%; min-height: 80px; }
.dg-funnel-stage { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 12px 8px; border-radius: var(--dg-radius-xs); transition: all 0.2s ease; position: relative; flex: 1; }
.dg-funnel-count { font-size: 18px; font-weight: 700; color: var(--dg-text-primary); }
.dg-funnel-rate { font-size: 12px; font-weight: 500; }
.dg-funnel-cost { font-size: 11px; color: var(--dg-text-tertiary); font-weight: 500; }
.dg-funnel-label { font-size: 11px; color: var(--dg-text-tertiary); font-weight: 500; margin-top: 2px; }
.dg-funnel-arrow { display: flex; align-items: center; color: var(--dg-text-caption); font-size: 20px; padding: 0 2px; }
/* Profitability Gauge */
.dg-gauge { height: 8px; border-radius: 4px; background: var(--dg-border-light); overflow: hidden; }
.dg-gauge-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }
.dg-gauge-safe { background: var(--dg-success); }
.dg-gauge-warning { background: var(--dg-warning); }
.dg-gauge-danger { background: var(--dg-error); }
/* Period efficiency */
.dg-period-efficient { border-left: 3px solid var(--dg-success) !important; }
.dg-period-inefficient { border-left: 3px solid var(--dg-error) !important; }
.dg-period-neutral { border-left: 3px solid var(--dg-border) !important; }
"""


def inject_theme() -> None:
    """Inject the brand CSS into the current page.

    Quasar 컴포넌트(업로더 헤더, 기본 버튼, 탭, 스위치 등)가 쓰는
    primary 색을 당근 오렌지로 바꿔 기본 파란색이 새는 것을 막는다.
    """
    ui.colors(
        primary="#FF6F0F",
        secondary="#52483C",
        accent="#FF8A30",
        positive="#00A84D",
        negative="#E5484D",
        info="#2196F3",
        warning="#F78C0C",
    )
    ui.add_css(BRAND_CSS)


def section_header(icon: str, title: str, subtitle: str = "") -> None:
    """Render a styled section header with icon badge."""
    with ui.row().classes("items-center gap-3 mb-4"):
        with ui.element("div").classes("dg-section-icon"):
            ui.icon(icon, size="20px")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("dg-section-title")
            if subtitle:
                ui.label(subtitle).classes("dg-section-subtitle")
