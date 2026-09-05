export enum LinkTypeEnum {
  "SHOP_PAGES" = "shop",
  "CUSTOM_LINK" = "custom",
}

export interface Link {
  path: string;
  name?: string;
  type: string;
  query?: Record<string, any>;
}

export const mobileLink = [
  {
    path: "/pages/index/index",
    name: "首页",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },

  {
    path: "/pages/user/user",
    name: "个人中心",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/collection/collection",
    name: "我的收藏",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/pages/customer_service/customer_service",
    name: "联系客服",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/user_set/user_set",
    name: "个人设置",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/pages/as_us/as_us",
    name: "关于我们",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/pages/user_data/user_data",
    name: "个人资料",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/pages/agreement/agreement",
    name: "隐私政策",
    query: {
      type: "privacy",
    },
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/pages/agreement/agreement",
    name: "服务协议",
    query: {
      type: "service",
    },
    type: LinkTypeEnum.SHOP_PAGES,
  },

  {
    path: "/packages/pages/recharge/recharge",
    name: "充值中心",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/ai_creation/ai_creation",
    name: "创作中心",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/drawing/drawing",
    name: "绘画",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/skills/skills",
    name: "技能大全",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
  {
    path: "/pages/follow_official/follow_official",
    name: "关注公众号",
    type: LinkTypeEnum.SHOP_PAGES,
    canTab: true,
  },
];

export const pcLink = [
  {
    path: "/",
    name: "首页对话",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/create",
    name: "AI创作",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/drawing",
    name: "AI绘画",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/skill",
    name: "AI技能",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/recharge",
    name: "充值奖励",
    type: LinkTypeEnum.SHOP_PAGES,
  },
  {
    path: "/user/collection",
    name: "我的收藏",
    type: LinkTypeEnum.SHOP_PAGES,
  },
];
