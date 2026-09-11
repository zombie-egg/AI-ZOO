<?php

namespace app\common\service\kiosk;

use GuzzleHttp\Client;

class KioskImageForgeService
{
    private Client $client;
    private string $token;

    public function __construct()
    {
        $baseUrl = rtrim((string)env('imageforge.base_url', 'http://imageforge:8000'), '/');
        $host = parse_url($baseUrl, PHP_URL_HOST);
        if (!in_array($host, ['imageforge', 'host.docker.internal', '127.0.0.1', 'localhost'], true)) {
            throw new \RuntimeException('ImageForge 必须通过本机或容器内网访问');
        }
        $this->token = (string)env('imageforge.internal_token', '');
        if ($this->token === '') {
            throw new \RuntimeException('IMAGEFORGE_INTERNAL_TOKEN 未配置');
        }
        $this->client = new Client(['base_uri' => $baseUrl, 'timeout' => 12]);
    }

    private function request(string $method, string $uri, array $options = []): array
    {
        $options['headers']['X-Internal-Token'] = $this->token;
        $options['headers']['Accept'] = 'application/json';
        $response = $this->client->request($method, $uri, $options);
        $payload = json_decode((string)$response->getBody(), true);
        if (!is_array($payload)) {
            throw new \RuntimeException('ImageForge 返回格式错误');
        }
        return $payload;
    }

    public function catalog(): array
    {
        return $this->request('GET', '/v4/scenes');
    }

    public function scenes(): array
    {
        return (array)($this->catalog()['scenes'] ?? []);
    }

    public function poses(): array
    {
        return (array)($this->catalog()['poses'] ?? []);
    }

    public function gallery(int $limit = 60): array
    {
        $limit = max(1, min(100, $limit));
        return $this->request('GET', '/v4/gallery?limit=' . $limit);
    }

    public function generate(string $orderNo, string $sceneId, string $poseId, array $participants, string $sku): array
    {
        return $this->request('POST', '/v4/generations', [
            'json' => [
                'order_no' => $orderNo,
                'scene_id' => $sceneId,
                'pose_id' => $poseId,
                'participants' => array_values($participants),
                'sku' => $sku,
            ],
        ]);
    }

    public function generationStatus(string $generationId): array
    {
        return $this->request('GET', '/v4/generations/' . rawurlencode($generationId));
    }

    public function approve(string $generationId): array
    {
        return $this->request('POST', '/v4/generations/' . rawurlencode($generationId) . '/approve');
    }

    public function deleteOrder(string $orderNo): void
    {
        $this->request('DELETE', '/internal/orders/' . rawurlencode($orderNo));
    }
}
