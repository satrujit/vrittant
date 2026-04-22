import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';

import '../../features/all_news/screens/all_news_screen.dart';
import '../../features/files/screens/files_screen.dart';
import '../../features/home/screens/home_screen.dart';
import '../../features/profile/screens/profile_screen.dart';
import '../l10n/app_strings.dart';
import '../theme/theme_extensions.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  late final PageController _pageController;
  int _currentIndex = 0;

  static const _screens = <Widget>[
    HomeScreen(),
    AllNewsScreen(),
    FilesScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _onTabTap(int index) {
    setState(() => _currentIndex = index);
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
    );
  }

  void _onPageChanged(int index) {
    setState(() => _currentIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final s = AppStrings.of(ref);

    return Scaffold(
      body: PageView(
        controller: _pageController,
        onPageChanged: _onPageChanged,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: t.navBg,
          border: Border(top: BorderSide(color: t.dividerColor, width: 0.5)),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(icon: LucideIcons.home, label: s.navHome, isActive: _currentIndex == 0, onTap: () => _onTabTap(0)),
                _NavItem(icon: LucideIcons.list, label: s.navAllStories, isActive: _currentIndex == 1, onTap: () => _onTabTap(1)),
                _NavItem(icon: LucideIcons.folderOpen, label: s.navFiles, isActive: _currentIndex == 2, onTap: () => _onTabTap(2)),
                _NavItem(icon: LucideIcons.settings, label: s.navSettings, isActive: _currentIndex == 3, onTap: () => _onTabTap(3)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: 70,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 20,
              color: isActive ? t.navActiveColor : t.navInactiveColor,
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                fontSize: 9,
                letterSpacing: 0.5,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                color: isActive ? t.navActiveColor : t.navInactiveColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
