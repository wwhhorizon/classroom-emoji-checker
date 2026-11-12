'use strict';

window.ui = SwaggerUIBundle({
  url: '/openapi.json',
  dom_id: '#swagger-ui',
  deepLinking: true,
  displayRequestDuration: true,
  persistAuthorization: false,
  queryConfigEnabled: false,
  validatorUrl: null,
  presets: [SwaggerUIBundle.presets.apis],
  layout: 'BaseLayout',
  requestInterceptor(request) {
    const target = new URL(request.url, window.location.origin);
    if (target.origin === window.location.origin && target.pathname.startsWith('/api/')) {
      request.headers['X-Requested-With'] = 'EmojiApp';
    }
    return request;
  },
});
