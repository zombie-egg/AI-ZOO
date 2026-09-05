<?php

declare(strict_types=1);

namespace app\api\http\middleware;

use app\common\service\JsonService;

/** Phase 1 裁剪模块入口守卫，防止自动路由绕过前端隐藏。 */
class Phase1ModuleGuardMiddleware
{
    private array $blockedControllers = [
        'feedback',
        'member',
        'share',
        'sms',
    ];

    private array $blockedUris = [
        'login/douyinmnplogin',
        'pay/notifymnpdy',
    ];

    public function handle($request, \Closure $next)
    {
        $controller = strtolower($request->controller());
        $uri = $controller . '/' . strtolower($request->action());

        if (in_array($controller, $this->blockedControllers, true)
            || in_array($uri, $this->blockedUris, true)) {
            return JsonService::fail('该功能已在 Phase 1 下线');
        }

        return $next($request);
    }
}
