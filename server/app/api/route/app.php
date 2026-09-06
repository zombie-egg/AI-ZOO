<?php

use think\facade\Route;

Route::group('kiosk', function () {
    Route::get('scenes', 'Kiosk/scenes');
    Route::post('create-order', 'Kiosk/createOrder');
    Route::post('order-scene/<id>', 'Kiosk/selectScene');
    Route::post('order-pose/<id>', 'Kiosk/selectPose');
    Route::post('order-photos/<id>', 'Kiosk/photos');
    Route::get('order-status/<id>', 'Kiosk/status');
    Route::post('order-pay/<id>', 'Kiosk/pay');
    Route::post('order-pay/<id>/simulate', 'Kiosk/simulatePay');
    Route::post('order-generate/<id>', 'Kiosk/generate');
    Route::get('order-generation-status/<id>', 'Kiosk/generationStatus');
    Route::post('order-approve/<id>', 'Kiosk/approveResult');
    Route::get('order-print-status/<id>', 'Kiosk/printStatus');
    Route::post('order-print-status/<id>', 'Kiosk/printStatus');
    Route::delete('order-data/<id>', 'Kiosk/deleteData');
});
