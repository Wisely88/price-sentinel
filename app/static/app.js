const { createApp, ref, reactive, onMounted } = Vue;

createApp({
  setup() {
    const currentTab = ref('search');
    const searchQuery = ref('');
    const loadingSearch = ref(false);
    const searchData = ref(null);
    const favorites = ref([]);
    const testingNotify = ref(false);

    const selectedPlatforms = reactive({
      jd: true,
      taobao: true,
      pdd: true,
    });

    const settings = reactive({
      enable_mac_notify: '1',
      bark_key: '',
      webhook_url: '',
      check_interval_hours: '4',
      price_drop_only: '1'
    });

    const toast = reactive({
      visible: false,
      message: '',
      timer: null
    });

    const favoriteModal = reactive({
      visible: false,
      item: null,
      targetPrice: ''
    });

    const showToast = (msg) => {
      toast.message = msg;
      toast.visible = true;
      if (toast.timer) clearTimeout(toast.timer);
      toast.timer = setTimeout(() => {
        toast.visible = false;
      }, 3000);
    };

    const formatDate = (isoString) => {
      if (!isoString) return '刚刚';
      try {
        const d = new Date(isoString);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return isoString;
      }
    };

    // --- Search Logic ---
    const executeSearch = async () => {
      const q = searchQuery.value.trim();
      if (!q) return;

      loadingSearch.value = true;
      searchData.value = null;

      const platforms = [];
      if (selectedPlatforms.jd) platforms.push('jd');
      if (selectedPlatforms.taobao) platforms.push('taobao');
      if (selectedPlatforms.pdd) platforms.push('pdd');

      try {
        const url = `/api/search?q=${encodeURIComponent(q)}&platforms=${platforms.join(',')}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Search failed');
        const data = await res.json();
        searchData.value = data;
        if (data.items.length === 0) {
          showToast('未找到匹配商品，建议换一个关键词');
        }
      } catch (err) {
        console.error(err);
        showToast('比价请求异常，请检查网络');
      } finally {
        loadingSearch.value = false;
      }
    };

    // --- Favorites Logic ---
    const loadFavorites = async () => {
      try {
        const res = await fetch('/api/favorites');
        const data = await res.json();
        favorites.value = data.items || [];
      } catch (err) {
        console.error(err);
      }
    };

    const openAddFavoriteModal = (item) => {
      favoriteModal.item = item;
      favoriteModal.targetPrice = '';
      favoriteModal.visible = true;
    };

    const confirmAddFavorite = async () => {
      if (!favoriteModal.item) return;
      const it = favoriteModal.item;
      const target = favoriteModal.targetPrice ? parseFloat(favoriteModal.targetPrice) : null;

      try {
        const res = await fetch('/api/favorites', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: it.title,
            platform: it.platform,
            url: it.url,
            current_price: it.final_price,
            target_price: target,
            item_id: it.item_id,
            image_url: it.image_url,
            discount_info: it.discount_tag
          })
        });

        if (res.ok) {
          showToast('已成功加入降价监控列表！');
          favoriteModal.visible = false;
          loadFavorites();
        } else {
          showToast('添加监控失败');
        }
      } catch (err) {
        console.error(err);
        showToast('网络异常');
      }
    };

    const removeFavorite = async (id) => {
      if (!confirm('确定要移除此商品的降价监控吗？')) return;
      try {
        const res = await fetch(`/api/favorites/${id}`, { method: 'DELETE' });
        if (res.ok) {
          showToast('已移除监控');
          loadFavorites();
        }
      } catch (err) {
        console.error(err);
      }
    };

    const triggerManualCheck = async (id) => {
      showToast('正在即时巡检最新价格...');
      try {
        const res = await fetch(`/api/favorites/${id}/check`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          showToast(`巡检完成: 最新价 ¥${data.new_price}${data.notified ? ' (已触发降价推送)' : ''}`);
          loadFavorites();
        } else {
          showToast('巡检完成，暂无价格变动');
        }
      } catch (err) {
        console.error(err);
        showToast('巡检失败');
      }
    };

    // --- Settings Logic ---
    const loadSettings = async () => {
      try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        Object.assign(settings, data);
      } catch (err) {
        console.error(err);
      }
    };

    const saveSettings = async () => {
      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings)
        });
        if (res.ok) {
          showToast('配置保存成功！');
        }
      } catch (err) {
        console.error(err);
        showToast('保存失败');
      }
    };

    const testNotification = async () => {
      testingNotify.value = true;
      try {
        const res = await fetch('/api/notify/test', { method: 'POST' });
        const data = await res.json();
        showToast('已触发测试通知，请检查 Mac 屏幕或手机！');
      } catch (err) {
        console.error(err);
        showToast('测试推送失败');
      } finally {
        testingNotify.value = false;
      }
    };

    onMounted(() => {
      loadFavorites();
      loadSettings();
    });

    return {
      currentTab,
      searchQuery,
      loadingSearch,
      searchData,
      selectedPlatforms,
      favorites,
      settings,
      toast,
      favoriteModal,
      testingNotify,
      executeSearch,
      loadFavorites,
      openAddFavoriteModal,
      confirmAddFavorite,
      removeFavorite,
      triggerManualCheck,
      loadSettings,
      saveSettings,
      testNotification,
      formatDate
    };
  }
}).mount('#app');
