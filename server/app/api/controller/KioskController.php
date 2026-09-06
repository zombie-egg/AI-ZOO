<?php

namespace app\api\controller;

use app\api\logic\KioskLogic;

class KioskController extends BaseApiController
{
    public array $notNeedLogin = [
        'scenes', 'createOrder', 'selectScene', 'selectPose', 'photos', 'status', 'pay', 'simulatePay',
        'generate', 'generationStatus', 'approveResult', 'printStatus', 'deleteData'
    ];

    public function initialize()
    {
        parent::initialize();
        $expected = (string)env('kiosk.device_proxy_token', '');
        $actual = (string)$this->request->header('X-Kiosk-Token', '');
        if ($expected === '' || !hash_equals($expected, $actual)) {
            throw new \RuntimeException('Kiosk 设备鉴权失败');
        }
    }

    public function createOrder()
    {
        try { return $this->data(KioskLogic::createOrder($this->request->post(), $this->userId)); }
        catch (\Throwable $e) { return $this->fail('K1001：' . $e->getMessage()); }
    }

    public function scenes()
    {
        try { return $this->data(KioskLogic::scenes()); }
        catch (\Throwable $e) { return $this->fail('K1000：' . $e->getMessage()); }
    }

    public function selectScene(int $id)
    {
        try { return $this->data(KioskLogic::selectScene($id, (string)$this->request->post('scene_id'))); }
        catch (\Throwable $e) { return $this->fail('K1002：' . $e->getMessage()); }
    }

    public function selectPose(int $id)
    {
        try { return $this->data(KioskLogic::selectPose($id, (string)$this->request->post('pose_id'))); }
        catch (\Throwable $e) { return $this->fail('K1010：' . $e->getMessage()); }
    }

    public function photos(int $id)
    {
        try {
            $action = (string)$this->request->post('action', 'upload');
            if ($action === 'consent') return $this->data(KioskLogic::recordConsent($id, $this->request->post()));
            return $this->data(KioskLogic::uploadPhoto(
                $id,
                (int)$this->request->post('participant_no', 1),
                (string)$this->request->post('shot_type'),
                $this->request->file('photo')
            ));
        } catch (\Throwable $e) { return $this->fail('K1002：' . $e->getMessage()); }
    }

    public function status(int $id)
    {
        try { return $this->data(KioskLogic::status($id)); }
        catch (\Throwable $e) { return $this->fail('K1003：' . $e->getMessage()); }
    }

    public function pay(int $id)
    {
        try { return $this->data(KioskLogic::createPayment($id, (string)$this->request->post('sku', 'print_1'))); }
        catch (\Throwable $e) { return $this->fail('K1004：' . $e->getMessage()); }
    }

    public function simulatePay(int $id)
    {
        try { return $this->data(KioskLogic::simulatePayment($id)); }
        catch (\Throwable $e) { return $this->fail('K1011：' . $e->getMessage()); }
    }

    public function generate(int $id)
    {
        try {
            return $this->data(KioskLogic::startGeneration(
                $id,
                (string)$this->request->post('sku', 'print_1'),
                filter_var($this->request->post('operator_test', false), FILTER_VALIDATE_BOOLEAN)
            ));
        }
        catch (\Throwable $e) { return $this->fail('K1005：' . $e->getMessage()); }
    }

    public function generationStatus(int $id)
    {
        try { return $this->data(KioskLogic::generationStatus($id)); }
        catch (\Throwable $e) { return $this->fail('K1006：' . $e->getMessage()); }
    }

    public function approveResult(int $id)
    {
        try { return $this->data(KioskLogic::approveResult($id)); }
        catch (\Throwable $e) { return $this->fail('K1007：' . $e->getMessage()); }
    }

    public function printStatus(int $id)
    {
        try {
            if ($this->request->isPost()) return $this->data(KioskLogic::reportPrint($id, $this->request->post()));
            return $this->data(KioskLogic::printStatus($id));
        } catch (\Throwable $e) { return $this->fail('K1008：' . $e->getMessage()); }
    }

    public function deleteData(int $id)
    {
        try { return $this->data(KioskLogic::deleteData($id)); }
        catch (\Throwable $e) { return $this->fail('K1009：' . $e->getMessage()); }
    }
}
