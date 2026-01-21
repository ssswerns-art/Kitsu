import React, { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import Button from "./common/custom-button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Input } from "./ui/input";
import { toast } from "sonner";
import { useAuthSelector } from "@/store/auth-store";
import { api } from "@/lib/api";

type FormData = {
  email: string;
  password: string;
  confirm_password: string;
};

function LoginPopoverButton() {
  const setAuth = useAuthSelector((state) => state.setAuth);
  const [formData, setFormData] = useState<FormData>({
    email: "",
    password: "",
    confirm_password: "",
  });
  const [tabValue, setTabValue] = useState<"login" | "signup">("login");

  const resolveTokens = (data: any) => ({
    accessToken:
      (data as any)?.access_token ||
      (data as any)?.accessToken ||
      (data as any)?.token,
    refreshToken:
      (data as any)?.refresh_token || (data as any)?.refreshToken,
  });

  const fetchProfile = async (
    accessToken: string,
  ): Promise<{ email: string; id: string }> => {
    const profile = await api.get("/users/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return {
      email: (profile.data as any).email,
      id: (profile.data as any).id,
    };
  };

  const loginWithEmail = async () => {
    if (formData.email === "" || formData.password === "") {
      toast.error("Please fill in all fields", {
        style: { background: "red" },
      });
      return;
    }

    const { data } = await api.post("/auth/login", {
      email: formData.email,
      password: formData.password,
    });

    const tokens = resolveTokens(data);
    if (!tokens.accessToken || !tokens.refreshToken) {
      throw new Error("Missing tokens in auth response");
    }

    const profile = await fetchProfile(tokens.accessToken);
    const userEmail = profile.email;
    const userId = profile.id;

    toast.success("Login successful", { style: { background: "green" } });
    clearForm();
    setAuth({
      id: userId,
      email: userEmail,
      username: userEmail.split("@")[0],
      avatar: "",
      collectionId: "",
      collectionName: "",
      autoSkip: false,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
    });
  };

  const signupWithEmail = async () => {
    if (formData.password === "" || formData.email === "" || formData.confirm_password === "") {
      toast.error("Please fill in all fields", {
        style: { background: "red" },
      });
      return;
    }

    if (formData.password !== formData.confirm_password) {
      toast.error("Passwords do not match", {
        style: { background: "red" },
      });
      return;
    }

    const { data } = await api.post("/auth/register", {
      email: formData.email,
      password: formData.password,
    });

    toast.success("Account created successfully. You are now logged in.", {
      style: { background: "green" },
    });
    const tokens = resolveTokens(data);
    if (!tokens.accessToken || !tokens.refreshToken) {
      throw new Error("Missing tokens in auth response");
    }

    const profile = await fetchProfile(tokens.accessToken);
    const userEmail = profile.email;
    const userId = profile.id;

    setAuth({
      id: userId,
      email: userEmail,
      username: userEmail.split("@")[0],
      avatar: "",
      collectionId: "",
      collectionName: "",
      autoSkip: false,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
    });
    clearForm();
    setTabValue("login");
  };

  const clearForm = () => {
    setFormData({
      email: "",
      password: "",
      confirm_password: "",
    });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="bg-white text-md text-black hover:bg-gray-200 hover:text-black transition-all duration-300"
        >
          Login
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        className="bg-black bg-opacity-50 backdrop-blur-sm w-[300px] mt-4 mr-4 p-4"
      >
        <Tabs
          defaultValue={tabValue}
          value={tabValue}
          onValueChange={(value) => setTabValue(value as "login" | "signup")}
        >
          <TabsList>
            <TabsTrigger onClick={clearForm} value="login">
              Login
            </TabsTrigger>
            <TabsTrigger onClick={clearForm} value="signup">
              Signup
            </TabsTrigger>
          </TabsList>
          <TabsContent value="login" className="flex flex-col gap-2">
            <div className="mt-2">
              <p className="text-gray-300 text-xs">Email:</p>
              <Input
                required
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                type="text"
                value={formData.email}
                placeholder="Enter your email"
              />
            </div>
            <div>
              <p className="text-gray-300 text-xs">Password:</p>
              <Input
                required
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                placeholder="Enter your password"
              />
            </div>
            <Button
              variant="default"
              className="w-full text-xs"
              size="sm"
              type="submit"
                onClick={loginWithEmail}
              >
                Login
              </Button>
          </TabsContent>
          <TabsContent value="signup" className="flex flex-col gap-2">
            <div>
              <p className="text-gray-300 text-xs">Email:</p>
              <Input
                required
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                type="email"
                placeholder="Enter your email"
              />
            </div>
            <div>
              <p className="text-gray-300 text-xs">Password:</p>
              <Input
                required
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                type="password"
                placeholder="Enter your password"
              />
            </div>
            <div>
              <p className="text-gray-300 text-xs">Confirm Password:</p>
              <Input
                required
                onChange={(e) =>
                  setFormData({ ...formData, confirm_password: e.target.value })
                }
                type="password"
                placeholder="Enter your password again"
              />
            </div>
            <Button
              variant="default"
              className="w-full text-xs"
              size="sm"
              type="submit"
              onClick={signupWithEmail}
            >
              Signup
            </Button>
          </TabsContent>
        </Tabs>
      </PopoverContent>
    </Popover>
  );
}

export default LoginPopoverButton;
