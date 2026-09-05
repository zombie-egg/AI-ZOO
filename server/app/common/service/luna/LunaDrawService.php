<?php

namespace app\common\service\luna;

use app\adminapi\logic\setting\LunaServiceSettingLogic;
use app\common\enum\BusinessErrorCodeEnum;
use app\common\enum\CacheTagEnum;
use app\common\exception\BaseException;
use app\common\types\luna\FaceMappingList;
use app\common\utils\CacheUtils;
use app\common\utils\LogUtils;
use GuzzleHttp\Client;
use think\Exception;
use think\facade\Cache;

class LunaDrawService
{
    private $host = 'https://prod.luna.aws.iartai.com';

    private $secret;
    private $secretKey;

    private $accessToken = null;
    private $accessTokenTTL = 14400;
    private $accessTokenCacheKey = "";

    private $client = null;

    private $systemConfig;

    // Luna算法上传图片同步OSS地址。默认无需改动
    const LUNA_OSS_BASE_URL = 'https://iart-user-upload-file.oss-cn-hangzhou.aliyuncs.com';

    public function __construct($systemConfig = null)
    {
        $runtimeHost = getenv('LUNA_BASE_URL');
        $this->host = rtrim((string)(($runtimeHost !== false && $runtimeHost !== '')
            ? $runtimeHost
            : env('luna.base_url', $this->host)), '/');
        if (self::isPhase1StubEnabled() || self::isImageForgeEnabled()) {
            $stubHost = parse_url($this->host, PHP_URL_HOST);
            // 两种本地模式共用同一组受限地址。ThinkPHP 的 .env 与容器环境变量
            // 加载顺序可能让模式标志仍显示为 stub，但实际 host 已指向宿主机 ImageForge。
            $allowedHosts = ['imageforge', 'host.docker.internal', 'luna-stub', '127.0.0.1', 'localhost'];
            if (!in_array($stubHost, $allowedHosts, true)) {
                throw new BaseException('本地算法服务只允许使用本机或 Compose 内网地址');
            }
            $systemConfig = [
                'secret' => (string)(getenv('LUNA_SECRET') ?: env('luna.secret', '')),
                'secret_key' => (string)(getenv('LUNA_SECRET_KEY') ?: env('luna.secret_key', '')),
            ];
        }
        if (empty($systemConfig)) {
            $systemConfig = (new LunaServiceSettingLogic())->getConfig();
        }
        $this->systemConfig = $systemConfig;
        if (empty($this->systemConfig['secret']) || empty($this->systemConfig['secret_key'])) {
            throw new BaseException("Luna算法服务配置不正确，请检查配置");
        }
        $this->secret = $this->systemConfig['secret'];
        $this->secretKey = $this->systemConfig['secret_key'];
        // CacheUtils logs cache misses, so never place the credential itself in the cache key.
        $this->accessTokenCacheKey = "luna_draw_token:" . hash('sha256', $this->secretKey);
        $this->client = new Client([
            'base_uri' => $this->host,
            'timeout' => 30,
        ]);
    }

    public static function isPhase1StubEnabled(): bool
    {
        $runtime = getenv('LUNA_PHASE1_STUB_ENABLED');
        return filter_var($runtime !== false ? $runtime : env('luna.phase1_stub_enabled', false), FILTER_VALIDATE_BOOLEAN);
    }

    public static function isImageForgeEnabled(): bool
    {
        $runtime = getenv('LUNA_UPSTREAM');
        return strtolower((string)($runtime !== false ? $runtime : env('luna.upstream', 'official'))) === 'imageforge';
    }

    public static function getOssBaseUrl(): string
    {
        return rtrim((string)env('luna.oss_base_url', self::LUNA_OSS_BASE_URL), '/');
    }

    public function getAccessToken($forceRefresh = false)
    {
        if ($forceRefresh) {
            Cache::delete($this->accessTokenCacheKey);
        }
        return CacheUtils::remember($this->accessTokenCacheKey, function () {
            $res = $this->sendRequest('POST', '/api/app/authentication', [
                'secret' => $this->secret,
                'secretKey' => $this->secretKey,
            ]);
            if (!isset($res['data']['accessToken'])) {
                throw new Exception("getAccessToken fail");
            }

            return $res['data']['accessToken'];
        }, $this->accessTokenTTL / 60 - 1, CacheTagEnum::LUNA_DRAW);
    }

    private function sendRequest($method, $uri, $params, $headers = [], $customerErrorHandler = null)
    {
        $logContext = [
            'method' => $method,
            'url' => $this->host . $uri,
            'headers' => $this->sanitizeForLog($headers),
            'payload' => $this->sanitizeForLog($params),
        ];
        LogUtils::log("Luna作图服务请求参数", $logContext);
        try {
            if ($method == 'GET') {
                $resp = $this->client->get($uri, [
                    'query' => $params,
                    'headers' => $headers
                ]);
            }
            if ($method == 'POST') {
                $resp = $this->client->post($uri, [
                    'json' => $params,
                    'headers' => $headers
                ]);
            }
            if ($method == 'UPLOAD') {
                $resp = $this->client->post($uri, [
                    'multipart' => [
                        [
                            'name' => 'file',
                            'contents' => \GuzzleHttp\Psr7\Utils::tryFopen($params['file_path'], 'r'),
                            'filename' => basename($params['file_path']),
                        ],
                    ],
                    'headers' => $headers
                ]);
            }
//            echo implode(' ', [$method, $uri]), PHP_EOL;
//            echo json_encode($params, JSON_UNESCAPED_UNICODE), PHP_EOL;
//            echo $resp->getBody(), PHP_EOL;
        } catch (\Exception $e) {
            if (strpos($e->getMessage(), 'timed out')) {
                $path = runtime_path('log');
                // 创建文件夹
                if (!is_dir($path)) {
                    mkdir($path, 0755, true);
                }
                $resp = $this->client->request('GET', '/', [
                    'debug' => fopen($path . 'debug.log', 'a')
                ]);
            }

            LogUtils::record($e, "请求上游失败", $logContext);
            throw $e;
        }

        $respData = json_decode($resp->getBody(), true);
        LogUtils::log("Luna作图服务响应", [
            'method' => $method,
            'url' => $this->host . $uri,
            'response' => $this->sanitizeForLog($respData),
        ]);
        if (empty($respData)) {
            $e = new Exception("call luna api fail: empty resp");
            LogUtils::record($e, "请求上游失败", $logContext);
            throw $e;
        }
        if ($respData['code'] !== 1) {
            // 强制刷新TOKEN，以防止缓存的TOKEN已经失效（正常情况下不会出现）
            if ($respData['code'] == 4002) {
                $this->getAccessToken(true);
            }

            if (is_callable($customerErrorHandler)) {
                return $customerErrorHandler($respData);
            }

//            header('content-type:application/json');
//            exit(json_encode([$respData]));
            throw new Exception($respData['message']);
        }
        return $respData;
    }

    /**
     * 日志必须保留协议形状，但不得写入凭据、令牌、用户本地文件路径或签名 URL 查询串。
     */
    private function sanitizeForLog($value, string $key = '')
    {
        $normalizedKey = strtolower(str_replace(['_', '-'], '', $key));
        if (in_array($normalizedKey, ['secret', 'secretkey', 'jwtheader', 'accesstoken'], true)) {
            return '<redacted>';
        }
        if ($normalizedKey === 'filepath') {
            return '<local-file-redacted>';
        }
        if (is_array($value)) {
            $sanitized = [];
            foreach ($value as $itemKey => $itemValue) {
                $sanitized[$itemKey] = $this->sanitizeForLog($itemValue, (string)$itemKey);
            }
            return $sanitized;
        }
        if (is_string($value) && preg_match('#^https?://#i', $value)) {
            $url = parse_url($value);
            if (!empty($url['query'])) {
                return sprintf('%s://%s%s?<signed-query-redacted>',
                    $url['scheme'] ?? 'https',
                    $url['host'] ?? '',
                    $url['path'] ?? ''
                );
            }
        }
        return $value;
    }

    function submitDrawingTaskV3(FaceMappingList $faceMappingList)
    {
        $res = $this->sendRequest('POST',
            '/api/userMessage/createSwapEnhanceV3',
            $faceMappingList->toArray(),
            [
                'JWTHEADER' => $this->getAccessToken()
            ]);
        return $res['data'];
    }

    /**
     * Kiosk 专用预览入口：携带订单号和模板号，ImageForge 才能执行免费重做限流与幂等追踪。
     */
    public function submitKioskPreview(FaceMappingList $faceMappingList, string $orderNo, int $templateId)
    {
        $res = $this->sendRequest('POST', '/api/userMessage/createSwapEnhanceV3', [
            'face_mappings' => $faceMappingList->toArray(),
            'order_no' => $orderNo,
            'template_id' => $templateId,
        ], [
            'JWTHEADER' => $this->getAccessToken(),
        ]);
        return $res['data'];
    }

    function pollTaskStatus($msgID, $isThumbnail = 0)
    {
        // todo java需要返回作图结果对应的模板id，方便定位做图异常问题
        try {
            $res = $this->sendRequest('GET', '/api/userMessage/polling', [
                'messageId' => $msgID,
                'isThumbnail' => $isThumbnail,
            ], [
                'JWTHEADER' => $this->getAccessToken()
            ]);
        } catch (\Exception $e) {
            if (strpos($e->getMessage(), 'frequent') || strpos($e->getMessage(), '频繁')) {
                return false;
            }
            return false;
        }
        return $res['data'];
    }

    function getMaterialFileFaceList($msgID)
    {
        try {
            $res = $this->sendRequest('GET', '/api/userMessage/getMaterialFileFaceList', [
                'id' => $msgID,
            ], [
                'JWTHEADER' => $this->getAccessToken()
            ]);
        } catch (\Exception $e) {
            if (strpos($e->getMessage(), 'frequent') || strpos($e->getMessage(), '频繁')) {
                return false;
            }
            return false;
        }
        return $res['data'];
    }

    function uploadFile($filePath)
    {
        $res = $this->sendRequest('UPLOAD', '/api/userMessage/checkUserImageUpload', [
            'file_path' => $filePath,
        ], [
            'JWTHEADER' => $this->getAccessToken()
        ], function ($respData) {
            $code = BusinessErrorCodeEnum::COMMON_ERROR;
            switch ($respData['code']) {
                case 6001:
                    //  "message": "请勿重复上传!",
                    throw new BaseException('重复上传。请换一张照片', $code);
                    break;
                case 9003:
                    //  "message": "en: eyeglasses | cn: 配戴眼镜!",
                    throw new BaseException('配戴眼镜。请换一张照片', $code);
                    break;
                case 9002:
                    //  "message": "en: face occluded | cn: 脸部被遮挡!",
                    throw new BaseException('脸部被遮挡。请换一张照片', $code);
                    break;
                case 9001:
                    //  "message": "en: Face detection failed | cn: 人脸检测失败!",
                    throw new BaseException('人脸检测失败。请换一张照片', $code);
                    break;
                case 9004:
                    //  "message": "en: celebrity | cn: 名人检测失败!",
                    throw new BaseException('名人检测失败。请换一张照片', $code);
                    break;
                case 9005:
                    //  "message": "en: Safety | cn: 安全检测失败!",
                    throw new BaseException('安全检测失败。请换一张照片', $code);
                    break;
                case 9006:
                    //  "message": "en: Facial deviation is too large | cn: 脸部偏移过大!",
                    throw new BaseException('脸部偏移过大。请换一张照片', $code);
                    break;
                case 9007:
                    // en: Insufficient quality and clarity | cn: 脸部清晰度不够!
                    throw new BaseException('脸部清晰度不够。请换一张照片', $code);
                    break;
                case 9008:
                    // en: No photos of children allowed | cn: 不允许上传儿童照片!
                    throw new BaseException('不允许上传儿童照片。请换一张照片', $code);
                    break;
                default:
                    throw new BaseException(sprintf('%s: %s', $respData['message'] ?? 'Upstream error happen', $respData['code'] ?? ''), $code);
            }
            return $respData;
        });
        return $res['data'];
    }

    static function clearCache()
    {
        $tag = CacheTagEnum::LUNA_DRAW;
        Cache::tag($tag)->clear();
    }

}
