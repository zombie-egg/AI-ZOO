import request, { baseUrl, requireLogin } from "../utils/request";
const accountInfo = uni.getAccountInfoSync ? uni.getAccountInfoSync() || {} : {};
export const miniProgramAppID = accountInfo.miniProgram?.appId || "";

export function getUserInfo(loginParam) {
  return request({
    url: "/api/user/info",
    method: "GET",
    preventLoading: true,
    loginParam,
  });
}

// 微信小程序登录
export function mnpLogin(data) {
  data.appid = miniProgramAppID;
  return request({
    url: "/api/login/mnpLogin",
    method: "POST",
    data,
    loginRequired: false,
  });
}

// 仅本机 Phase 1 离线验收使用；服务端在生产环境对该入口返回 404。
export function phase1OfflineLogin() {
  return request({
    url: "/api/login/phase1OfflineLogin",
    method: "POST",
    loginRequired: false,
  });
}

export function uploadCommonImage(filePath) {
  const token = uni.getStorageSync("token");

  // 如果存在 token，则将其添加到请求头中
  let header;
  if (token) {
    header = { token };
  } else {
    requireLogin();
    return Promise.reject(new Error("No token found"));
  }

  return uni.uploadFile({
    url: `${baseUrl}/api/upload/image`,
    filePath: filePath,
    name: "file",
    header: header,
  });
}
