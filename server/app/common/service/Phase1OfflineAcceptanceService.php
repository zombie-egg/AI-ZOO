<?php

namespace app\common\service;

class Phase1OfflineAcceptanceService
{
    public static function enabled(): bool
    {
        return filter_var(env('phase1.offline_acceptance', false), FILTER_VALIDATE_BOOLEAN);
    }

    public static function requestAllowed($request): bool
    {
        if (!self::enabled()) {
            return false;
        }
        $host = strtolower((string)$request->host());
        $host = explode(':', $host)[0];
        return in_array($host, ['127.0.0.1', 'localhost'], true);
    }
}
