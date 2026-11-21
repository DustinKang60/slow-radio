// 지구본 라디오 서비스워커
// ⚠️ index.html 등 에셋을 고치면 CACHE_NAME 버전을 반드시 올릴 것.
//    안 올리면 기기가 캐시된 옛 코드를 계속 써서 "수정이 반영 안 됨"으로 오판하게 된다.
const CACHE_NAME = 'globe-radio-v111';
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-180.png',
  './icons/icon-32.png'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

// 주의: dustinkang60.github.io 의 앱들은 저장 공간(Cache Storage)을 함께 쓴다.
// 자기 이름으로 시작하는 캐시만 지워야 한다 — 전부 지우면 다른 앱(골프일기 등)의 오프라인 저장분이
// 날아가 그 앱이 해외·오프라인에서 아예 안 열린다.
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith('globe-radio-') && k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// 앱 셸만 캐시 우선. 유튜브 등 외부 요청은 건드리지 않는다.
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
      const copy = res.clone();
      caches.open(CACHE_NAME).then(c => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match('./index.html')))
  );
});
