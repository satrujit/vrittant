class User {
  final String id;
  final String name;
  final String phone;
  final String? email;
  final String? avatarUrl;
  final String orgId;
  final String orgName;

  const User({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.avatarUrl,
    required this.orgId,
    required this.orgName,
  });
}
