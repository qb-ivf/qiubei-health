# admin-web · 逑贝互联网医院运营管理后台（Vue3 + Element Plus）

PC 端运营管理后台，对应 PRD「子系统3：运营总管理后台」与「子系统3.4：药师审方」。供医院行政、财务、药师、运营团队使用。

## 技术栈
Vue 3 + Vite + Vue Router + Pinia + Element Plus + Axios。

## 目录结构
```
admin-web/
├── src/
│   ├── api/request.js        # axios 封装（JWT 注入 / 401 拦截）
│   ├── router/index.js       # 路由 + 登录守卫
│   ├── layouts/MainLayout.vue
│   └── views/  Login / Dashboard(监管面板) / PharmacistReview(药师审方)
│                / DoctorAudit(资质终审) / Drugs(药品字典) / Finance(财务提现)
├── vite.config.js            # /api 代理到 FastAPI(127.0.0.1:8000)
└── package.json
```

## 启动
```bash
npm install
npm run dev        # http://localhost:5173
```
> 当前各页为接 mock 的脚手架；联调时把 `views/*` 内操作替换为 `@/api/request` 调用后端接口。
> 登录账号任意（mock）；接入后端后走 RBAC（行政/药师/财务/运营角色）。
