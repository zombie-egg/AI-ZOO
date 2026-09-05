<?php

namespace app\api\controller;

use app\api\validate\SwapTemplateValidate;
use app\common\model\swap_template\SwapStrategy;
use app\common\model\swap_template\SwapStrategyGroupRelation;
use app\common\model\swap_template\SwapTemplate;
use app\common\model\swap_template\SwapTemplateGroup;
use think\db\Query;

class SwapTemplateController extends BaseApiController
{
    private const PHASE1_ALLOWED_STRATEGY_ID = 2;

    public array $notNeedLogin = [
        'strategyList',
        'groupList',
        'templateList',
    ];

    // 玩法列表
    function strategyList()
    {
        $res['strategyList'] = SwapStrategy::where([
            'status' => 1,
            'id' => self::PHASE1_ALLOWED_STRATEGY_ID,
        ])->select();
        return $this->success("success", $res);
    }

    // 指定玩法下的模板组列表
    function groupList()
    {
        $params = (new SwapTemplateValidate())->get()->goCheck('groupList');
        if ((int)$params['id'] !== self::PHASE1_ALLOWED_STRATEGY_ID) {
            return $this->fail('该玩法已在 Phase 1 下线');
        }
        $rows = SwapTemplateGroup::alias('stg')
            ->with([
                'templates' => function (Query $query) {
                    $query->where(['status' => 1])->order(['sort' => 'desc', 'id' => 'desc']);
                }
            ])
            ->join('swap_strategy_group_relation ssgr', 'stg.id = ssgr.group_id')
            ->where('ssgr.strategy_id', $params['id'])
            ->where(['stg.status' => 1])
            ->order(['ssgr.sort' => 'desc', 'ssgr.id' => 'desc'])
            ->field(['stg.*', 'ssgr.id as relation_id', 'ssgr.sort', 'ssgr.create_time as create_time'])
            ->select();
        $res['groupList'] = $rows;
        return $this->success("success", $res);
    }

    // 指定模板组中的模板列表
    function templateList()
    {
        $params = (new SwapTemplateValidate())->get()->goCheck('templateList');
        $groupEnabled = SwapStrategyGroupRelation::where([
            'strategy_id' => self::PHASE1_ALLOWED_STRATEGY_ID,
            'group_id' => $params['id'],
        ])->find();
        if (!$groupEnabled) {
            return $this->fail('该模板组已在 Phase 1 下线');
        }
        $rows = SwapTemplate::alias('st')
            ->join('swap_template_group_relation stgr', 'st.id = stgr.template_id')
            ->where('stgr.group_id', $params['id'])
            ->where(['st.status' => 1])
            ->order(['stgr.sort' => 'desc', 'stgr.id' => 'desc'])
            ->field(['st.*', 'stgr.id as relation_id', 'stgr.sort', 'stgr.create_time as create_time'])
            ->select();
        $res['templateList'] = $rows;
        return $this->success("success", $res);
    }


}
