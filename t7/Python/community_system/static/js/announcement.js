/**
 * 公告相关交互功能
 */

// 初始化公告功能
document.addEventListener('DOMContentLoaded', function() {
    initAnnouncementCards();
    initAnnouncementModal();
});

/**
 * 初始化公告卡片交互
 */
function initAnnouncementCards() {
    const cards = document.querySelectorAll('.announcement-clickable');
    
    cards.forEach(card => {
        // 添加点击效果
        card.addEventListener('mouseenter', function() {
            this.classList.add('card-hover');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('card-hover');
        });
        
        // 添加点击音效（如果需要）
        card.addEventListener('click', function(e) {
            // 添加点击动画效果
            this.style.transform = 'translateY(-3px) scale(0.98)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
}

/**
 * 初始化公告模态框（如果需要模态框显示）
 */
function initAnnouncementModal() {
    // 为未来可能的模态框功能预留
    console.log('公告模态框功能已初始化');
}

/**
 * 显示公告详情（备用方案：模态框）
 */
function showAnnouncementModal(announcementId) {
    // 如果需要用模态框显示公告详情，可以使用这个函数
    fetch(`/announcements/${announcementId}/`)
        .then(response => response.json())
        .then(data => {
            // 创建和显示模态框
            const modal = createAnnouncementModal(data);
            document.body.appendChild(modal);
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
        })
        .catch(error => {
            console.error('获取公告详情失败:', error);
        });
}

/**
 * 创建公告模态框HTML
 */
function createAnnouncementModal(announcement) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'announcementModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">${announcement.title}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <span class="badge bg-primary me-2">${announcement.type_display}</span>
                        <small class="text-muted">${announcement.created_at}</small>
                    </div>
                    <div class="announcement-content">
                        ${announcement.content}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <a href="/announcements/${announcement.announcement_id}/" class="btn btn-primary">查看完整页面</a>
                </div>
            </div>
        </div>
    `;
    return modal;
}

// 导出函数供其他模块使用
window.AnnouncementUtils = {
    showModal: showAnnouncementModal,
    initCards: initAnnouncementCards
};
