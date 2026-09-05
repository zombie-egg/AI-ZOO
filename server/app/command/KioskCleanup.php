<?php
declare(strict_types=1);

namespace app\command;

use app\api\logic\KioskLogic;
use app\common\model\kiosk\KioskOrder;
use think\console\Command;
use think\console\Input;
use think\console\Output;

class KioskCleanup extends Command
{
    protected function configure()
    {
        $this->setName('kiosk:cleanup')->setDescription('物理删除过期 Kiosk 照片与生成图');
    }

    protected function execute(Input $input, Output $output)
    {
        $orders = KioskOrder::where('expire_time', '>', 0)->where('expire_time', '<=', time())->where('status', '<>', 'deleted')->limit(100)->select();
        foreach ($orders as $order) {
            try { KioskLogic::deleteData((int)$order->id); $output->writeln('deleted ' . $order->order_no); }
            catch (\Throwable $error) { $output->writeln('failed ' . $order->order_no . ': ' . $error->getMessage()); }
        }
        return 0;
    }
}

