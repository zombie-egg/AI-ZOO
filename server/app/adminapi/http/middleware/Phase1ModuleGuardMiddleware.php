<?php

declare(strict_types=1);

namespace app\adminapi\http\middleware;

use app\common\service\JsonService;

/**
 * Phase 1 裁剪模块入口守卫。
 *
 * 上游使用自动路由，仅隐藏菜单不能阻止直接调用接口，因此在控制器执行前
 * 统一拒绝已裁剪模块。数据库表与业务代码暂时保留，便于后续有审计地回滚。
 */
class Phase1ModuleGuardMiddleware
{
    private array $blockedControllers = [
        'article.article',
        'article.articlecate',
        'feedback',
        'member.memberbenefits',
        'member.memberorder',
        'member.memberpackage',
        'member.memberpackagecomment',
        'notice.smsconfig',
        'setting.sharesetting',
        'task.taskinvite',
        'task.taskshare',
        'tools.generator',
    ];

    private array $blockedUris = [
        'swap_template.template/incollectiontemplatelists',
        'swap_template.template/notincollectiontemplatelists',
        'swap_template.template/addchild',
        'swap_template.template/removechild',
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
